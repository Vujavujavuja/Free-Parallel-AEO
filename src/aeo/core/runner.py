"""Model runner: fan the question payload out across the target panel
concurrently, with retries (in the provider), truncation auto-continue, a global
cost cap, and per-model failure tolerance (PRD FR-8..FR-13)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from aeo.constants import PromptMode
from aeo.core.prompting import render_answer
from aeo.logging import get_logger
from aeo.providers.base import ChatMessage, ChatResult, LLMProvider
from aeo.schemas.question import Question
from aeo.schemas.run import ModelResponseRecord, RunOptions

log = get_logger(__name__)

ProgressCb = Callable[[int, int, str], Awaitable[None]] | None
LogCb = Callable[[str], Awaitable[None]] | None


def describe_response(r: ModelResponseRecord) -> str:
    """One-line human-readable summary of a model response for the live log."""
    if r.error:
        return f"{r.model_id}: ERROR — {r.error}"
    tokens = r.prompt_tokens + r.completion_tokens
    extra: list[str] = []
    if r.web_search_used:
        extra.append(f"{len(r.search_queries)} searches")
    if r.continuations:
        extra.append(f"{r.continuations} continuation(s)")
    suffix = " · " + ", ".join(extra) if extra else ""
    return f"{r.model_id}: {tokens} tok, ${r.cost_usd:.4f}, {r.latency_ms}ms{suffix}"

_ANSWER_SYSTEM = ChatMessage(
    role="system",
    content=(
        "You are a helpful research assistant. Answer as you naturally would, "
        "recommending whichever vendors genuinely fit."
    ),
)


class _CostGovernor:
    """Thread-safe running cost total with a hard cap."""

    def __init__(self, cap: float) -> None:
        self._cap = cap
        self._spent = 0.0
        self._lock = asyncio.Lock()

    @property
    def spent(self) -> float:
        return self._spent

    async def add(self, amount: float) -> None:
        async with self._lock:
            self._spent += amount

    async def exceeded(self) -> bool:
        async with self._lock:
            return self._spent >= self._cap


async def run_models(
    provider: LLMProvider,
    questions: list[Question],
    options: RunOptions,
    on_progress: ProgressCb = None,
    log_cb: LogCb = None,
    brand: str | None = None,
) -> list[ModelResponseRecord]:
    """Execute the fan-out and return one record per (model[, question])."""
    semaphore = asyncio.Semaphore(max(1, options.concurrency))
    governor = _CostGovernor(options.cost_cap_usd)

    # Build the unit-of-work list depending on prompt mode.
    if options.prompt_mode == PromptMode.PER_QUESTION:
        units = [(model, [q]) for model in options.target_models for q in questions]
    else:
        units = [(model, questions) for model in options.target_models]

    total = len(units)
    done = 0
    done_lock = asyncio.Lock()
    records: list[ModelResponseRecord] = []

    async def worker(model: str, qs: list[Question]) -> ModelResponseRecord:
        nonlocal done
        async with semaphore:
            record = await _run_unit(provider, qs, model, options, governor, brand)
        async with done_lock:
            done += 1
            current = done
        if log_cb:
            await log_cb(describe_response(record))
        if on_progress:
            await on_progress(current, total, model)
        return record

    tasks = [asyncio.create_task(worker(model, qs)) for model, qs in units]
    for coro in asyncio.as_completed(tasks):
        records.append(await coro)

    # Stable ordering: by target-model order, then question index.
    order = {m: i for i, m in enumerate(options.target_models)}
    records.sort(key=lambda r: (order.get(r.model_id, 1_000), r.question_index or 0))
    return records


async def _run_unit(
    provider: LLMProvider,
    questions: list[Question],
    model: str,
    options: RunOptions,
    governor: _CostGovernor,
    brand: str | None = None,
) -> ModelResponseRecord:
    q_index = questions[0].index if options.prompt_mode == PromptMode.PER_QUESTION else None
    record = ModelResponseRecord(model_id=model, question_index=q_index)

    if await governor.exceeded():
        record.error = "cost_cap_reached"
        return record

    prompt = render_answer(questions, options.enable_web_search, brand, options.language)
    messages = [_ANSWER_SYSTEM, ChatMessage(role="user", content=prompt)]
    try:
        await _chat_with_continue(provider, model, messages, options, record)
    except Exception as exc:
        record.error = f"{type(exc).__name__}: {exc}"
        log.warning("model_failed", model=model, error=record.error)
        return record

    await governor.add(record.cost_usd)
    return record


async def _chat_with_continue(
    provider: LLMProvider,
    model: str,
    messages: list[ChatMessage],
    options: RunOptions,
    record: ModelResponseRecord,
) -> None:
    """Call the model, auto-continuing on truncation up to max_continuations."""
    contents: list[str] = []
    queries: set[str] = set()
    citations: list[str] = []
    continuations = 0

    while True:
        result: ChatResult = await provider.chat(
            model,
            messages,
            max_tokens=options.max_tokens,
            enable_web_search=options.enable_web_search,
        )
        contents.append(result.content)
        record.prompt_tokens += result.prompt_tokens
        record.completion_tokens += result.completion_tokens
        record.cost_usd += result.cost_usd
        record.latency_ms += result.latency_ms
        record.web_search_used = record.web_search_used or result.web_search_used
        queries.update(result.search_queries)
        citations.extend(result.search_citations)
        record.finish_reason = result.finish_reason

        if result.finish_reason != "length" or continuations >= options.max_continuations:
            break
        continuations += 1
        messages = [
            *messages,
            ChatMessage(role="assistant", content=result.content),
            ChatMessage(role="user", content="Please continue exactly where you left off."),
        ]

    record.content = "".join(contents)
    record.search_queries = sorted(queries)
    record.search_citations = list(dict.fromkeys(citations))
    record.continuations = continuations

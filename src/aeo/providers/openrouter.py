"""OpenRouter provider: async httpx client with retries, cost accounting, and
optional web search (PRD FR-8..FR-13, §9.2, §14)."""

from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from aeo.exceptions import ProviderError
from aeo.logging import get_logger
from aeo.providers.base import ChatMessage, ChatResult, LLMProvider, ModelInfo
from aeo.settings import Settings, get_settings

log = get_logger(__name__)

_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


class OpenRouterProvider(LLMProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        key = self._settings.openrouter_api_key.get_secret_value()
        if not key:
            raise ProviderError(
                "OPENROUTER_API_KEY is not set. Add it to .env to run against real models."
            )
        self._client = httpx.AsyncClient(
            base_url=self._settings.openrouter_base_url,
            timeout=self._settings.openrouter_timeout_seconds,
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": self._settings.openrouter_http_referer,
                "X-Title": self._settings.openrouter_x_title,
                "Content-Type": "application/json",
            },
        )
        self._pricing: dict[str, tuple[float, float]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float = 0.3,
        enable_web_search: bool = False,
        response_schema: dict[str, object] | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "usage": {"include": True},
        }
        if enable_web_search:
            payload["plugins"] = [{"id": "web"}]
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "strict": True,
                    "schema": response_schema,
                },
            }

        started = time.perf_counter()
        data = await self._post("/chat/completions", payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return self._parse_chat(model, data, latency_ms, enable_web_search)

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1.0, max=30.0),
        reraise=True,
    )
    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = await self._client.post(path, json=payload)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        if result.get("error"):
            raise ProviderError(str(result["error"]))
        return result

    def _parse_chat(
        self, model: str, data: dict[str, Any], latency_ms: int, requested_search: bool
    ) -> ChatResult:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(f"No choices returned for model {model!r}.")
        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        annotations = message.get("annotations") or []
        # OpenRouter web plugin returns url_citation annotations for searched pages.
        search_citations: list[str] = []
        for ann in annotations:
            url = (ann.get("url_citation") or {}).get("url") if isinstance(ann, dict) else None
            if url:
                search_citations.append(url)
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        cost = usage.get("cost")
        cost_usd = float(cost) if cost is not None else self._estimate_cost(
            model, prompt_tokens, completion_tokens
        )
        return ChatResult(
            model=model,
            content=content,
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            web_search_used=bool(search_citations) or requested_search,
            search_citations=search_citations,
        )

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        prices = self._pricing.get(model)
        if not prices:
            return 0.0
        p_in, p_out = prices
        return prompt_tokens * p_in + completion_tokens * p_out

    async def list_models(self) -> list[ModelInfo]:
        resp = await self._client.get("/models")
        resp.raise_for_status()
        payload = resp.json()
        models: list[ModelInfo] = []
        for row in payload.get("data", []):
            pricing = row.get("pricing") or {}
            p_in = _to_float(pricing.get("prompt"))
            p_out = _to_float(pricing.get("completion"))
            self._pricing[row["id"]] = (p_in, p_out)
            models.append(
                ModelInfo(
                    id=row["id"],
                    name=row.get("name", ""),
                    context_length=row.get("context_length"),
                    prompt_price=p_in,
                    completion_price=p_out,
                )
            )
        return models


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

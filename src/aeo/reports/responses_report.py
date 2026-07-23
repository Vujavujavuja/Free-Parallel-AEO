"""Markdown export of the full raw model responses (shareable, diffable).

The complete answer text is already stored per run in ``run.json``; this renders
it as a single Markdown file so responses can be shared and reviewed outside the
tool (per the AI-mentions report requirements)."""

from __future__ import annotations

from pathlib import Path

from aeo.schemas.run import RunRecord


def write_responses_md(record: RunRecord, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f"# Raw model responses — {record.company.name}",
        "",
        f"- Run: `{record.id}`",
        f"- Date: {record.created_at:%Y-%m-%d %H:%M UTC}",
        f"- Models: {len(record.options.target_models)} · "
        f"Questions: {len(record.questions)} · "
        f"Cost: ${record.total_cost_usd:.4f} · "
        f"Web search: {'on' if record.options.enable_web_search else 'off'}",
        "",
        "## Questions",
        "",
    ]
    for q in record.questions:
        lines.append(f"{q.index}. {q.text}")
    lines.append("")

    # Order responses by target-model order, then question index.
    order = {m: i for i, m in enumerate(record.options.target_models)}
    responses = sorted(
        record.responses, key=lambda r: (order.get(r.model_id, 999), r.question_index or 0)
    )
    for r in responses:
        lines.append("---")
        lines.append("")
        header = f"## {r.model_id}"
        if r.question_index is not None:
            header += f" — Q{r.question_index}"
        lines.append(header)
        lines.append("")
        meta = (
            f"tokens {r.prompt_tokens + r.completion_tokens} "
            f"({r.prompt_tokens} in / {r.completion_tokens} out) · "
            f"${r.cost_usd:.4f} · {r.latency_ms} ms · "
            f"finish `{r.finish_reason or 'n/a'}`"
        )
        if r.web_search_used:
            meta += f" · web search ({len(r.search_queries)} queries)"
        if r.continuations:
            meta += f" · {r.continuations} continuation(s)"
        lines.append(f"> {meta}")
        lines.append("")
        if r.error:
            lines.append(f"**Error:** {r.error}")
        else:
            lines.append(r.content or "_(empty)_")
        lines.append("")
        if r.search_queries:
            lines.append("**Searches performed:**")
            lines.extend(f"- {q}" for q in r.search_queries)
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path

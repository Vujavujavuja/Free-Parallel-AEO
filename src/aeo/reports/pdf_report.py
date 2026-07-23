"""PDF report with charts (PRD FR-21 visual deliverable).

matplotlib renders the charts (provenance pie, brand mentions bar, competitor
share-of-voice bar, mention heatmap) to in-memory PNGs; reportlab assembles the
document. No system dependencies beyond the Python packages.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from aeo.analysis import AnalysisResult
from aeo.reports.base import get_analysis
from aeo.schemas.run import RunRecord

_RUST = "#a0522d"
_BLUE = "#3b82f6"
_GREEN = "#22c55e"
_SLATE = "#64748b"
_PROV_COLORS = {"organic": _GREEN, "search_driven": _BLUE, "absent": _SLATE}


def _fig_image(fig: Any, width_cm: float) -> Image:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width_cm * cm
    img.drawHeight = width_cm * cm * ratio
    return img


def _provenance_pie(analysis: AnalysisResult) -> Any:
    counts = dict.fromkeys(("organic", "search_driven", "absent"), 0)
    for m in analysis.models:
        counts[m.provenance.value] += 1
    labels = [k for k, v in counts.items() if v]
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.pie(
        [counts[k] for k in labels],
        labels=[k.replace("_", " ") for k in labels],
        colors=[_PROV_COLORS[k] for k in labels],
        autopct="%1.0f%%",
        startangle=90,
    )
    ax.set_title("Provenance")
    return fig


def _brand_bar(analysis: AnalysisResult) -> Any:
    ranked = analysis.ranked_models()
    if not ranked:
        return None
    names = [m.model_id.split("/")[-1] for m in ranked]
    vals = [m.brand_mentions for m in ranked]
    fig, ax = plt.subplots(figsize=(6, max(2.4, 0.4 * len(names))))
    ax.barh(names[::-1], vals[::-1], color=_RUST)
    ax.set_title("Brand mentions by model")
    ax.tick_params(labelsize=8)
    return fig


def _competitor_bar(analysis: AnalysisResult) -> Any:
    totals: dict[str, int] = {}
    for m in analysis.models:
        for c, v in m.competitor_totals.items():
            totals[c] = totals.get(c, 0) + v
    items = sorted(((c, v) for c, v in totals.items() if v), key=lambda x: x[1])
    if not items:
        return None
    fig, ax = plt.subplots(figsize=(6, max(2.4, 0.4 * len(items))))
    ax.barh([c for c, _ in items], [v for _, v in items], color=_BLUE)
    ax.set_title("Competitor share of voice")
    ax.tick_params(labelsize=8)
    return fig


def _heatmap(analysis: AnalysisResult) -> Any:
    models = analysis.models
    q = analysis.question_indices
    if not models or not q:
        return None
    grid = [[m.per_question_brand.get(qi, 0) for qi in q] for m in models]
    fig, ax = plt.subplots(figsize=(6, max(2.4, 0.4 * len(models))))
    im = ax.imshow(grid, cmap="Oranges", aspect="auto")
    ax.set_xticks(range(len(q)), [f"Q{i}" for i in q], fontsize=7)
    ax.set_yticks(range(len(models)), [m.model_id.split("/")[-1] for m in models], fontsize=7)
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            if val:
                ax.text(c, r, str(val), ha="center", va="center", fontsize=6)
    ax.set_title("Mention heatmap (model x question)")
    fig.colorbar(im, ax=ax, shrink=0.7)
    return fig


def write_pdf(record: RunRecord, path: Path) -> Path:
    analysis = get_analysis(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=colors.HexColor(_RUST))
    body = ParagraphStyle("body", parent=styles["BodyText"], alignment=TA_LEFT, spaceAfter=4)
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=f"AI Visibility — {record.company.name}")
    story: list[object] = []

    story.append(Paragraph(f"AI Visibility Report — {record.company.name}", h1))
    story.append(Paragraph(
        f"{len(record.options.target_models)} models &middot; {len(record.questions)} questions "
        f"&middot; cost ${record.total_cost_usd:.4f}",
        body,
    ))
    story.append(Spacer(1, 0.4 * cm))

    mentioning = sum(1 for m in analysis.models if m.brand_mentions > 0)
    total_mentions = sum(m.brand_mentions for m in analysis.models)
    stat_rows = [
        ["Models mentioning brand", f"{mentioning}/{len(analysis.models)}"],
        ["Total brand mentions", str(total_mentions)],
        ["Questions", str(len(analysis.question_indices))],
        ["Competitors tracked", str(len(analysis.competitors))],
    ]
    stat_tbl = Table(stat_rows, colWidths=[7 * cm, 4 * cm])
    stat_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1eae4")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 0.4 * cm))

    for fig in (_provenance_pie(analysis), _brand_bar(analysis),
                _competitor_bar(analysis), _heatmap(analysis)):
        if fig is not None:
            story.append(_fig_image(fig, 15))
            story.append(Spacer(1, 0.3 * cm))

    if analysis.insights:
        story.append(Paragraph("Insights", styles["Heading2"]))
        for ins in analysis.insights:
            story.append(Paragraph(f"&bull; {_esc(ins)}", body))
        story.append(Spacer(1, 0.3 * cm))

    if analysis.domain_frequency:
        story.append(Paragraph("Top cited domains", styles["Heading2"]))
        rows = [["Domain", "#Models", "Brand", "Ref"]]
        for d in analysis.domain_frequency[:12]:
            rows.append([d.domain, str(d.num_models),
                         "Yes" if d.brand_owned else "", "Yes" if d.is_reference else ""])
        tbl = Table(rows, colWidths=[8 * cm, 2.5 * cm, 2 * cm, 2 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_RUST)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.3 * cm))

    if analysis.quotes:
        story.append(Paragraph("Representative quotes", styles["Heading2"]))
        for qt in analysis.quotes[:8]:
            story.append(Paragraph(
                f"&ldquo;{_esc(qt.get('quote', ''))}&rdquo; "
                f"<font color='{_SLATE}'>&mdash; {_esc(qt.get('model', ''))}</font>",
                body,
            ))

    doc.build(story)
    return path


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

"""PDF report with charts (PRD FR-21 visual deliverable).

Editorial design: warm paper, ink text, ember/wine accents, serif display, mono
labels. matplotlib renders styled charts to in-memory PNGs; reportlab assembles
the document with an executive summary, per-question reads, and a footer.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from aeo.analysis import AnalysisResult
from aeo.reports import theme as T
from aeo.reports.base import get_analysis
from aeo.schemas.run import RunRecord

# --- matplotlib global styling ---------------------------------------------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "text.color": T.INK,
    "axes.labelcolor": T.DUNE,
    "xtick.color": T.DUNE,
    "ytick.color": T.DUNE,
    "axes.edgecolor": T.RULE,
    "axes.linewidth": 0.8,
    "figure.facecolor": "none",
    "axes.facecolor": "none",
    "savefig.facecolor": "none",
    "font.size": 9,
})
_HEATMAP_CMAP = LinearSegmentedColormap.from_list("ember", T.HEATMAP_STOPS)

SERIF = "Times-Roman"
SERIF_B = "Times-Bold"
SERIF_I = "Times-Italic"
MONO = "Courier"
MONO_B = "Courier-Bold"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    ink, ember, wine, dune = (
        HexColor(T.INK), HexColor(T.EMBER), HexColor(T.WINE), HexColor(T.DUNE)
    )
    return {
        "kicker": ParagraphStyle("kicker", parent=base, fontName=MONO_B, fontSize=8,
                                 textColor=ember, spaceAfter=3, leading=10),
        "title": ParagraphStyle("title", parent=base, fontName=SERIF_B, fontSize=30,
                                 textColor=ink, leading=32, spaceAfter=2),
        "meta": ParagraphStyle("meta", parent=base, fontName=MONO, fontSize=8.5,
                               textColor=dune, spaceAfter=2, leading=12),
        "h2": ParagraphStyle("h2", parent=base, fontName=SERIF_B, fontSize=15,
                             textColor=ember, spaceBefore=10, spaceAfter=4, leading=17),
        "lead": ParagraphStyle("lead", parent=base, fontName=SERIF, fontSize=12,
                               textColor=ink, leading=17, spaceAfter=6, alignment=TA_LEFT),
        "body": ParagraphStyle("body", parent=base, fontName=SERIF, fontSize=10,
                               textColor=ink, leading=14.5, spaceAfter=3),
        "cap": ParagraphStyle("cap", parent=base, fontName=SERIF_I, fontSize=8.5,
                              textColor=dune, leading=11, spaceAfter=6),
        "quote": ParagraphStyle("quote", parent=base, fontName=SERIF_I, fontSize=11,
                                textColor=ink, leading=15, spaceAfter=2, leftIndent=8),
        "quoteby": ParagraphStyle("quoteby", parent=base, fontName=MONO, fontSize=8,
                                  textColor=wine, spaceAfter=8, leftIndent=8),
        "kpi_num": ParagraphStyle("kpi_num", parent=base, fontName=SERIF_B, fontSize=22,
                                  textColor=ember, leading=24),
        "kpi_lbl": ParagraphStyle("kpi_lbl", parent=base, fontName=MONO, fontSize=7.5,
                                  textColor=dune, leading=10),
        "tbl": ParagraphStyle("tbl", parent=base, fontName=SERIF, fontSize=9,
                              textColor=ink, leading=12),
        "tbl_h": ParagraphStyle("tbl_h", parent=base, fontName=SERIF_B, fontSize=9,
                                textColor=white, leading=12),
        "tbl_i": ParagraphStyle("tbl_i", parent=base, fontName=SERIF_I, fontSize=9,
                                textColor=HexColor(T.INK_SOFT), leading=12),
    }


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- charts -----------------------------------------------------------------

def _fig_image(fig: Any, width_cm: float) -> Image:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    img.drawWidth = width_cm * cm
    img.drawHeight = width_cm * cm * (img.imageHeight / img.imageWidth)
    return img


def _style_ax(ax: Any) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def _provenance_donut(analysis: AnalysisResult) -> Any:
    counts = dict.fromkeys(("organic", "search_driven", "absent"), 0)
    for m in analysis.models:
        counts[m.provenance.value] += 1
    labels = [k for k in counts if counts[k]]
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    ax.pie(
        [counts[k] for k in labels],
        labels=[k.replace("_", " ") for k in labels],
        colors=[T.PROVENANCE[k] for k in labels],
        autopct=lambda p: f"{p*sum(counts.values())/100:.0f}",
        startangle=90, wedgeprops={"width": 0.42, "edgecolor": T.PAPER, "linewidth": 2},
        textprops={"fontsize": 9},
    )
    ax.set_title("Provenance", fontsize=11, color=T.INK, fontweight="bold")
    return fig


def _brand_bar(analysis: AnalysisResult) -> Any:
    ranked = analysis.ranked_models()
    if not ranked:
        return None
    names = [m.model_id.split("/")[-1] for m in ranked][::-1]
    vals = [m.brand_mentions for m in ranked][::-1]
    fig, ax = plt.subplots(figsize=(4.0, max(2.4, 0.34 * len(names))))
    ax.barh(names, vals, color=T.EMBER, height=0.7)
    for i, v in enumerate(vals):
        if v:
            ax.text(v, i, f" {v}", va="center", fontsize=7.5, color=T.DUNE)
    ax.set_title("Brand mentions by model", fontsize=11, color=T.INK, fontweight="bold")
    ax.tick_params(labelsize=7.5)
    _style_ax(ax)
    return fig


def _competitor_bar(analysis: AnalysisResult) -> Any:
    totals: dict[str, int] = {}
    for m in analysis.models:
        for c, v in m.competitor_totals.items():
            totals[c] = totals.get(c, 0) + v
    items = sorted(((c, v) for c, v in totals.items() if v), key=lambda x: x[1])
    if not items:
        return None
    fig, ax = plt.subplots(figsize=(7.6, max(2.4, 0.36 * len(items))))
    ax.barh([c for c, _ in items], [v for _, v in items], color=T.WINE, height=0.7)
    for i, (_, v) in enumerate(items):
        ax.text(v, i, f" {v}", va="center", fontsize=7.5, color=T.DUNE)
    ax.set_title("Competitor share of voice (total mentions)", fontsize=11,
                 color=T.INK, fontweight="bold")
    ax.tick_params(labelsize=8)
    _style_ax(ax)
    return fig


def _heatmap(analysis: AnalysisResult) -> Any:
    models, q = analysis.models, analysis.question_indices
    if not models or not q:
        return None
    grid = [[m.per_question_brand.get(qi, 0) for qi in q] for m in models]
    fig, ax = plt.subplots(figsize=(7.6, max(2.6, 0.36 * len(models))))
    ax.imshow(grid, cmap=_HEATMAP_CMAP, aspect="auto")
    ax.set_xticks(range(len(q)), [f"Q{i}" for i in q], fontsize=7.5)
    ax.set_yticks(range(len(models)), [m.model_id.split("/")[-1] for m in models],
                  fontsize=7.5)
    vmax = max((max(r) for r in grid), default=0)
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            if val:
                ax.text(c, r, str(val), ha="center", va="center", fontsize=6.2,
                        color=T.INK if val < vmax * 0.6 else T.PAPER)
    ax.set_title("Mention heatmap — model x question", fontsize=11, color=T.INK,
                 fontweight="bold")
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    return fig


# --- narrative --------------------------------------------------------------

def _exec_summary(record: RunRecord, a: AnalysisResult) -> tuple[str, str]:
    brand = record.company.name
    n = len(a.models)
    mentioning = sum(1 for m in a.models if m.brand_mentions > 0)
    total = sum(m.brand_mentions for m in a.models)
    org = sum(1 for m in a.models if m.provenance.value == "organic")
    sd = sum(1 for m in a.models if m.provenance.value == "search_driven")
    absent = sum(1 for m in a.models if m.provenance.value == "absent")
    comp_totals: dict[str, int] = {}
    for m in a.models:
        for c, v in m.competitor_totals.items():
            comp_totals[c] = comp_totals.get(c, 0) + v
    top_comp = max(comp_totals.items(), key=lambda kv: kv[1], default=("—", 0))
    brand_owned_models = len({
        m.model_id for m in a.models for c in m.citations if c.brand_owned
    })
    cat = record.company.category or "this category"

    lead = (
        f"This report measures how {n} AI models describe <b>{cat}</b> when asked "
        f"{len(record.questions)} neutral buyer questions — none of which name "
        f"<b>{brand}</b> or its competitors. Because the prompts never mention the "
        f"brand, every mention below reflects what a model surfaces on its own "
        f"(its training knowledge) or finds through live web search — not prompting. "
        f"That makes this a measure of genuine, <i>organic</i> AI visibility."
    )
    absent_txt = f", while {absent} never mentioned it" if absent else ""
    summary = (
        f"<b>{mentioning} of {n}</b> models surfaced {brand} at least once, for "
        f"<b>{total}</b> total mentions across the question set. Visibility breaks down "
        f"as {org} organic and {sd} search-driven{absent_txt}. The most-mentioned "
        f"competitor across all models was <b>{_esc(top_comp[0])}</b> "
        f"({top_comp[1]} mentions). {brand}-owned domains were cited by "
        f"{brand_owned_models} of {n} models."
    )
    return lead, summary


# --- assembly ---------------------------------------------------------------

def _decorate(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFillColor(HexColor(T.PAPER))
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setStrokeColor(HexColor(T.EMBER))
    canvas.setLineWidth(1)
    canvas.line(2 * cm, 1.35 * cm, A4[0] - 2 * cm, 1.35 * cm)
    canvas.setFont(MONO, 7)
    canvas.setFillColor(HexColor(T.DUNE))
    canvas.drawString(2 * cm, 1.0 * cm, "GENERATED BY PARALLEL-AEO")
    canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"PAGE {doc.page}")
    canvas.restoreState()


def _kpi_row(record: RunRecord, a: AnalysisResult, st: dict[str, ParagraphStyle]) -> Table:
    n = len(a.models)
    mentioning = sum(1 for m in a.models if m.brand_mentions > 0)
    total = sum(m.brand_mentions for m in a.models)
    sd = sum(1 for m in a.models if m.provenance.value == "search_driven")
    sd_pct = f"{round(100 * sd / n)}%" if n else "0%"
    tiles = [
        (f"{mentioning}/{n}", "MODELS MENTIONING"),
        (str(total), "TOTAL MENTIONS"),
        (sd_pct, "SEARCH-DRIVEN"),
        (str(len(a.competitors)), "COMPETITORS TRACKED"),
    ]
    cells = [
        [Paragraph(v, st["kpi_num"]), Paragraph(lbl, st["kpi_lbl"])]
        for v, lbl in tiles
    ]
    tbl = Table([cells], colWidths=[4.15 * cm] * 4)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(T.PARCHMENT)),
        ("LINEABOVE", (0, 0), (-1, 0), 2, HexColor(T.EMBER)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def _two_up(left: Any, right: Any) -> Table | None:
    imgs = [i for i in (left, right) if i is not None]
    if not imgs:
        return None
    row = [_fig_image(left, 7.4) if left else "",
           _fig_image(right, 7.4) if right else ""]
    t = Table([row], colWidths=[8.2 * cm, 8.2 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return t


def write_pdf(record: RunRecord, path: Path) -> Path:
    a = get_analysis(record)
    st = _styles()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.7 * cm, bottomMargin=2 * cm,
        title=f"AI Visibility — {record.company.name}",
    )
    S: list[Any] = []

    # Header
    S.append(Paragraph("PARALLEL-AEO &middot; AI VISIBILITY REPORT", st["kicker"]))
    S.append(Paragraph(_esc(record.company.name), st["title"]))
    S.append(Paragraph(
        f"{len(record.options.target_models)} models &nbsp;/&nbsp; "
        f"{len(record.questions)} questions &nbsp;/&nbsp; "
        f"${record.total_cost_usd:.4f} spend"
        + (" &nbsp;/&nbsp; web search on" if record.options.enable_web_search else ""),
        st["meta"],
    ))
    S.append(Spacer(1, 0.2 * cm))
    S.append(HRFlowable(width="100%", thickness=1, color=HexColor(T.RULE)))
    S.append(Spacer(1, 0.3 * cm))

    # Executive summary
    lead, summary = _exec_summary(record, a)
    S.append(Paragraph("Executive summary", st["h2"]))
    S.append(Paragraph(lead, st["lead"]))
    S.append(Paragraph(summary, st["body"]))
    S.append(Spacer(1, 0.3 * cm))
    S.append(_kpi_row(record, a, st))
    S.append(Spacer(1, 0.4 * cm))

    # Provenance & visibility
    S.append(Paragraph("Provenance &amp; visibility", st["h2"]))
    S.append(Paragraph(
        "Left: whether each model's brand visibility is <i>organic</i> (from its own "
        "training knowledge) or <i>search-driven</i> (found via live web search). "
        "Right: total brand mentions per model, ranked.", st["cap"]))
    two = _two_up(_provenance_donut(a), _brand_bar(a))
    if two:
        S.append(two)
    S.append(Spacer(1, 0.3 * cm))

    # Competitive landscape
    comp = _competitor_bar(a)
    if comp:
        S.append(Paragraph("Competitive landscape", st["h2"]))
        S.append(Paragraph(
            "How often each competitor is named across all models — the share of "
            "voice the brand is up against.", st["cap"]))
        S.append(_fig_image(comp, 15.0))
        S.append(Spacer(1, 0.3 * cm))

    # Question coverage heatmap
    hm = _heatmap(a)
    if hm:
        S.append(Paragraph("Question-level coverage", st["h2"]))
        S.append(Paragraph(
            "Darker cells mean more brand mentions for that model on that question. "
            "This reveals which buyer questions surface the brand and which leave gaps.",
            st["cap"]))
        S.append(_fig_image(hm, 15.0))
        S.append(Spacer(1, 0.3 * cm))

    # Per-question read (AI interpretations)
    if a.questions:
        S.append(Paragraph("Per-question read", st["h2"]))
        rows = [[Paragraph(h, st["tbl_h"]) for h in
                 ("Q", "Question", "Mentions", "Models", "Read")]]
        for q in a.questions:
            rows.append([
                Paragraph(str(q.index), st["tbl"]),
                Paragraph(_esc(q.text), st["tbl"]),
                Paragraph(str(q.total_mentions), st["tbl"]),
                Paragraph(f"{q.models_mentioning}/{len(a.models)}", st["tbl"]),
                Paragraph(_esc(q.interpretation), st["tbl_i"]),
            ])
        tbl = Table(rows, colWidths=[0.8 * cm, 4.7 * cm, 2.0 * cm, 1.5 * cm, 6.5 * cm],
                    repeatRows=1)
        tbl.setStyle(_data_style(header=True))
        S.append(tbl)
        S.append(Spacer(1, 0.3 * cm))

    # Key findings
    if a.insights:
        S.append(Paragraph("Key findings", st["h2"]))
        for ins in a.insights:
            S.append(Paragraph(f"<font color='{T.EMBER}'>&#9642;</font> {_esc(ins)}", st["body"]))
        S.append(Spacer(1, 0.3 * cm))

    # Domains
    if a.domain_frequency:
        S.append(Paragraph("Where models get their information", st["h2"]))
        S.append(Paragraph(
            "The sites cited across answers. Brand-owned domains and your reference "
            "sites are flagged.", st["cap"]))
        rows = [[Paragraph(h, st["tbl_h"]) for h in
                 ("Domain", "Models citing", "Brand-owned", "Reference")]]
        for d in a.domain_frequency[:14]:
            rows.append([
                Paragraph(_esc(d.domain), st["tbl"]),
                Paragraph(str(d.num_models), st["tbl"]),
                Paragraph("&#10003;" if d.brand_owned else "", st["tbl"]),
                Paragraph("&#10003;" if d.is_reference else "", st["tbl"]),
            ])
        tbl = Table(rows, colWidths=[8.0 * cm, 3.0 * cm, 2.5 * cm, 2.0 * cm], repeatRows=1)
        tbl.setStyle(_data_style(header=True))
        S.append(tbl)
        S.append(Spacer(1, 0.3 * cm))

    # Quotes
    if a.quotes:
        S.append(Paragraph("In their words", st["h2"]))
        for qt in a.quotes[:8]:
            S.append(Paragraph(f"&ldquo;{_esc(qt.get('quote', ''))}&rdquo;", st["quote"]))
            S.append(Paragraph(f"&mdash; {_esc(qt.get('model', ''))}", st["quoteby"]))

    doc.build(S, onFirstPage=_decorate, onLaterPages=_decorate)
    return path


def _data_style(header: bool = False) -> TableStyle:
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor(T.RULE)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor(T.RULE_SOFT)]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(T.INK)),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("LINEBELOW", (0, 0), (-1, 0), 1, HexColor(T.EMBER)),
        ]
    return TableStyle(cmds)

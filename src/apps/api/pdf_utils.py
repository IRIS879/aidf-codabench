"""
Utility functions for generating model card PDFs using ReportLab.
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Colour palette ──────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1a237e")   # deep indigo – header bg
BRAND_LIGHT  = colors.HexColor("#e8eaf6")   # pale indigo – section header
ACCENT       = colors.HexColor("#3949ab")   # medium indigo – rule / label
TEXT_DARK    = colors.HexColor("#212121")
TEXT_MUTED   = colors.HexColor("#757575")
WHITE        = colors.white


def _build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "mc_title",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "mc_subtitle",
            fontName="Helvetica",
            fontSize=11,
            textColor=colors.HexColor("#c5cae9"),
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "section_header": ParagraphStyle(
            "mc_section_hdr",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=BRAND_DARK,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "mc_label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=ACCENT,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "mc_body",
            fontName="Helvetica",
            fontSize=10,
            textColor=TEXT_DARK,
            leading=14,
            spaceAfter=6,
        ),
        "meta": ParagraphStyle(
            "mc_meta",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_MUTED,
            alignment=TA_CENTER,
        ),
    }


# ── Human-readable key labels ────────────────────────────────────────────────
_LABEL_MAP = {
    "model_name": "Model Name",
    "task":       "Task",
    "output":     "Output",
    "overview":   "Overview",
}


def _pretty_label(key: str) -> str:
    """Convert a snake_case key to a Title Case label."""
    return _LABEL_MAP.get(key, key.replace("_", " ").title())


def generate_model_card_pdf(
    model_card_data: dict,
    submission_name: str = "",
    competition_name: str = "",
    team_name: str = "",
    submitted_at: str = "",
) -> bytes:
    """
    Generate a PDF model card from a dict of model card fields.

    Returns raw PDF bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Model Card",
    )

    styles = _build_styles()
    story = []

    # ── Header banner ─────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("MODEL CARD", styles["title"]),
    ]]
    if competition_name:
        header_data.append([Paragraph(competition_name, styles["subtitle"])])

    header_table = Table(header_data, colWidths=[doc.width])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # ── Submission meta table ─────────────────────────────────────────────────
    meta_rows = []
    if submission_name:
        meta_rows.append(["Submission", submission_name])
    if team_name:
        meta_rows.append(["Team", team_name])
    if submitted_at:
        meta_rows.append(["Submitted", submitted_at])

    if meta_rows:
        meta_style = ParagraphStyle(
            "meta_cell",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEXT_DARK,
            leading=12,
        )
        label_style = ParagraphStyle(
            "meta_label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=ACCENT,
            leading=12,
        )
        formatted = [
            [Paragraph(r[0], label_style), Paragraph(r[1], meta_style)]
            for r in meta_rows
        ]
        meta_table = Table(formatted, colWidths=[3.5 * cm, doc.width - 3.5 * cm])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BRAND_LIGHT),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, 0), 10),
            ("LEFTPADDING",   (1, 0), (1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BRAND_LIGHT, WHITE]),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

    # ── Divider ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=10))

    # ── Model card fields ─────────────────────────────────────────────────────
    if model_card_data:
        story.append(Paragraph("Model Information", styles["section_header"]))

        for key, value in model_card_data.items():
            if value is None:
                continue
            label = _pretty_label(key)
            story.append(Paragraph(label, styles["label"]))

            text = str(value).strip()
            # Escape XML special chars for ReportLab Paragraph
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Preserve newlines as line breaks
            text = text.replace("\n", "<br/>")
            story.append(Paragraph(text, styles["body"]))

    else:
        story.append(Paragraph("No model card data available.", styles["body"]))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TEXT_MUTED, spaceAfter=6))
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph(f"Generated on {generated_at}", styles["meta"]))

    doc.build(story)
    return buf.getvalue()

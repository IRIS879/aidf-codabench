"""
Utility functions for generating PDFs using ReportLab.

Values in the model card dict are rendered intelligently:
  - str / int / float / bool  →  plain paragraph
  - list of scalars           →  bullet list
  - dict (all short scalars)  →  compact 2-column shaded table
  - dict (long text / nested) →  sub-label per key, value recursed
Empty values (None, "", [], {}) are silently skipped at every level.
"""
import io
import json
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Colour palette ────────────────────────────────────────────────────────────
BRAND_DARK  = colors.HexColor("#1a237e")   # deep indigo – header bg
BRAND_LIGHT = colors.HexColor("#e8eaf6")   # pale indigo – meta band
ACCENT      = colors.HexColor("#3949ab")   # medium indigo – labels / rules
TEXT_DARK   = colors.HexColor("#212121")
TEXT_MUTED  = colors.HexColor("#757575")
WHITE       = colors.white
ROW_EVEN    = colors.HexColor("#f5f5f5")


# ── Styles ────────────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    return {
        "title": ParagraphStyle(
            "mc_title",
            fontName="Helvetica-Bold", fontSize=22,
            textColor=WHITE, alignment=TA_CENTER, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "mc_subtitle",
            fontName="Helvetica", fontSize=11,
            textColor=colors.HexColor("#c5cae9"), alignment=TA_CENTER, spaceAfter=2,
        ),
        "section_header": ParagraphStyle(
            "mc_section_hdr",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=BRAND_DARK, spaceBefore=10, spaceAfter=6,
        ),
        "label": ParagraphStyle(
            "mc_label",
            fontName="Helvetica-Bold", fontSize=9,
            textColor=ACCENT, spaceBefore=6, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "mc_body",
            fontName="Helvetica", fontSize=10,
            textColor=TEXT_DARK, leading=14, spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "mc_meta",
            fontName="Helvetica", fontSize=8,
            textColor=TEXT_MUTED, alignment=TA_CENTER,
        ),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

_LABEL_MAP = {
    "model_name": "Model Name",
    "task":       "Task",
    "output":     "Output",
    "overview":   "Overview",
}


def _pretty_label(key: str) -> str:
    return _LABEL_MAP.get(key, key.replace("_", " ").title())


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_empty(value) -> bool:
    """Recursively return True when value carries no displayable content."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (int, float, bool)):
        return False          # 0 / False are valid displayable values
    if isinstance(value, (list, dict)):
        items = value.values() if isinstance(value, dict) else value
        return not value or all(_is_empty(v) for v in items)
    return False


# ── Recursive renderer ────────────────────────────────────────────────────────

def _render_dict_table(
    data: dict,
    story: list,
    styles: dict,
    avail_width: float,
    left_indent: float = 0,
) -> None:
    """Render a flat all-scalar dict as a compact 2-column shaded table."""
    effective = avail_width - left_indent
    key_w = min(effective * 0.35, 4 * cm)
    val_w = effective - key_w

    key_st = ParagraphStyle(
        "_tbl_key", parent=styles["label"],
        leftIndent=0, spaceBefore=0, spaceAfter=1, fontSize=8,
    )
    val_st = ParagraphStyle(
        "_tbl_val", parent=styles["body"],
        leftIndent=0, spaceAfter=1, fontSize=9, leading=12,
    )

    rows = [
        [Paragraph(_pretty_label(k), key_st),
         Paragraph(_xml_escape(str(v)), val_st)]
        for k, v in data.items()
    ]

    tbl = Table(rows, colWidths=[key_w, val_w])
    tbl.setStyle(TableStyle([
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
        ("LEFTPADDING",    (0, 0), (0, -1), 6),
        ("LEFTPADDING",    (1, 0), (1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ("LINEBELOW",      (0, 0), (-1, -2), 0.3, colors.HexColor("#e0e0e0")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [ROW_EVEN, WHITE]),
    ]))

    if left_indent:
        # Wrap in outer table to apply left indentation
        outer = Table([[tbl]], colWidths=[effective])
        outer.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (0, 0), left_indent),
            ("TOPPADDING",    (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING",  (0, 0), (0, 0), 0),
        ]))
        story.append(outer)
    else:
        story.append(tbl)

    story.append(Spacer(1, 4))


def _render_value(
    value,
    story: list,
    styles: dict,
    avail_width: float,
    depth: int = 0,
) -> None:
    """
    Recursively render *value* into ReportLab flowables appended to *story*.

    Dispatch
    ────────
    str / int / float / bool  →  indented Paragraph
    list                      →  bullet items (scalars) or recurse (dicts/lists)
    dict – all values short   →  compact 2-column shaded table
    dict – long text / nested →  sub-label per key + value recursed
    """
    if _is_empty(value):
        return

    indent = depth * 10   # pt – left-indent per nesting level

    # ── scalar ────────────────────────────────────────────────────────────────
    if isinstance(value, (str, int, float, bool)):
        text = _xml_escape(str(value).strip()).replace("\n", "<br/>")
        st = ParagraphStyle(f"_body_d{depth}", parent=styles["body"], leftIndent=indent)
        story.append(Paragraph(text, st))

    # ── list ──────────────────────────────────────────────────────────────────
    elif isinstance(value, list):
        for item in value:
            if _is_empty(item):
                continue
            if isinstance(item, (dict, list)):
                _render_value(item, story, styles, avail_width, depth)
            else:
                text = _xml_escape(str(item).strip())
                st = ParagraphStyle(
                    f"_bullet_d{depth}", parent=styles["body"],
                    leftIndent=indent + 14, firstLineIndent=-10,
                )
                story.append(Paragraph(f"• {text}", st))

    # ── dict ──────────────────────────────────────────────────────────────────
    elif isinstance(value, dict):
        non_empty = {k: v for k, v in value.items() if not _is_empty(v)}
        if not non_empty:
            return

        all_scalar = all(isinstance(v, (str, int, float, bool)) for v in non_empty.values())
        # Use compact table only when all values fit on roughly one line each
        use_table = all_scalar and all(len(str(v)) <= 80 for v in non_empty.values())

        if use_table:
            _render_dict_table(non_empty, story, styles, avail_width, left_indent=indent)
        else:
            for k, v in non_empty.items():
                sub_st = ParagraphStyle(
                    f"_sublabel_d{depth}", parent=styles["label"],
                    leftIndent=indent, spaceBefore=4, spaceAfter=2,
                )
                story.append(Paragraph(_pretty_label(k), sub_st))
                _render_value(v, story, styles, avail_width, depth + 1)


# ── Public API ────────────────────────────────────────────────────────────────

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
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="Model Card",
    )

    styles = _build_styles()
    story = []

    # ── Header banner ──────────────────────────────────────────────────────────
    header_data = [[Paragraph("MODEL CARD", styles["title"])]]
    if competition_name:
        header_data.append([Paragraph(_xml_escape(competition_name), styles["subtitle"])])

    header_table = Table(header_data, colWidths=[doc.width])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # ── Submission meta table ──────────────────────────────────────────────────
    meta_rows = []
    if submission_name:
        meta_rows.append(["Submission", submission_name])
    if team_name:
        meta_rows.append(["Team", team_name])
    if submitted_at:
        meta_rows.append(["Submitted", submitted_at])

    if meta_rows:
        meta_st = ParagraphStyle(
            "meta_cell", fontName="Helvetica", fontSize=9,
            textColor=TEXT_DARK, leading=12,
        )
        lbl_st = ParagraphStyle(
            "meta_label", fontName="Helvetica-Bold", fontSize=9,
            textColor=ACCENT, leading=12,
        )
        formatted = [
            [Paragraph(r[0], lbl_st), Paragraph(_xml_escape(r[1]), meta_st)]
            for r in meta_rows
        ]
        meta_table = Table(formatted, colWidths=[3.5 * cm, doc.width - 3.5 * cm])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, -1), BRAND_LIGHT),
            ("TOPPADDING",     (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
            ("LEFTPADDING",    (0, 0), (-1, 0), 10),
            ("LEFTPADDING",    (1, 0), (1, -1), 8),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BRAND_LIGHT, WHITE]),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

    # ── Divider ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=6))

    # ── Model card fields ──────────────────────────────────────────────────────
    if model_card_data:
        story.append(Paragraph("Model Information", styles["section_header"]))

        for key, value in model_card_data.items():
            if _is_empty(value):
                continue
            story.append(Paragraph(_pretty_label(key), styles["label"]))
            _render_value(value, story, styles, doc.width)

    else:
        story.append(Paragraph("No model card data available.", styles["body"]))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TEXT_MUTED, spaceAfter=6))
    story.append(Paragraph(
        f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        styles["meta"],
    ))

    doc.build(story)
    return buf.getvalue()


def generate_leaderboard_pdf(
    leaderboard_title: str,
    leaderboard_rows: dict,
    competition_name: str = "",
) -> bytes:
    """
    Generate a simple printable PDF for one leaderboard.

    ``leaderboard_rows`` is expected to follow the structure returned by
    ``CompetitionViewSet.collect_leaderboard_data`` for a single leaderboard.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=leaderboard_title,
    )

    styles = _build_styles()
    story = []

    header_data = [[Paragraph("LEADERBOARD", styles["title"])]]
    if competition_name:
        header_data.append([Paragraph(_xml_escape(competition_name), styles["subtitle"])])
    header_data.append([Paragraph(_xml_escape(leaderboard_title), styles["subtitle"])])

    header_table = Table(header_data, colWidths=[doc.width])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    if not leaderboard_rows:
        story.append(Paragraph("No leaderboard entries available.", styles["body"]))
        doc.build(story)
        return buf.getvalue()

    def _leaderboard_cell_text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            try:
                text = json.dumps(value, ensure_ascii=False)
            except Exception:
                text = str(value)
        else:
            text = str(value)
        text = " ".join(text.split())
        if len(text) > 180:
            text = text[:177] + "..."
        return text

    columns = list(next(iter(leaderboard_rows.values())).keys())
    headers = ["Username"] + columns

    cell_style = ParagraphStyle(
        "lb_cell",
        fontName="Helvetica",
        fontSize=8,
        textColor=TEXT_DARK,
        leading=10,
    )
    header_style = ParagraphStyle(
        "lb_header",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=WHITE,
        leading=10,
        alignment=TA_CENTER,
    )

    rows = [[Paragraph(_xml_escape(str(col)), header_style) for col in headers]]
    for username, values in leaderboard_rows.items():
        row = [username] + [values.get(col, "") for col in columns]
        rows.append([
            Paragraph(_xml_escape(_leaderboard_cell_text(value)), cell_style)
            for value in row
        ])

    first_col_width = min(max(doc.width * 0.18, 4 * cm), 7 * cm)
    remaining = max(doc.width - first_col_width, 1)
    other_col_width = remaining / max(len(columns), 1)
    col_widths = [first_col_width] + [other_col_width] * len(columns)

    table = LongTable(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd8dc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_EVEN]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        styles["meta"],
    ))

    doc.build(story)
    return buf.getvalue()


def generate_frontend_leaderboard_pdf(
    leaderboard_title: str,
    leaderboard_payload: dict,
) -> bytes:
    """
    Generate a PDF from the same payload returned by ``PhaseViewSet.get_leaderboard``.
    This mirrors the readable leaderboard table shown on the frontend rather than
    the raw admin export structure.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=leaderboard_title,
    )

    styles = _build_styles()
    story = []

    header_data = [
        [Paragraph("LEADERBOARD", styles["title"])],
        [Paragraph(_xml_escape(leaderboard_title), styles["subtitle"])],
    ]
    header_table = Table(header_data, colWidths=[doc.width])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    tasks = leaderboard_payload.get("tasks") or []
    columns = []
    for task in tasks:
        for column in (task.get("columns") or []):
            columns.append({
                "task_name": task.get("name") or "",
                "title": column.get("title") or "",
                "index": column.get("index"),
                "key": column.get("key"),
            })

    def _score_for_column(submission, column):
        for score in submission.get("scores") or []:
            if score.get("index") == column.get("index") or score.get("column_key") == column.get("key"):
                return score.get("score", "")
        return ""

    def _format_date(date_text):
        return (date_text or "").replace("T", " ")[:16]

    def _cell(value):
        text = "" if value is None else str(value)
        text = " ".join(text.split())
        if len(text) > 120:
            text = text[:117] + "..."
        return Paragraph(_xml_escape(text), cell_style)

    header_style = ParagraphStyle(
        "frontend_lb_header",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=WHITE,
        leading=10,
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "frontend_lb_cell",
        fontName="Helvetica",
        fontSize=8,
        textColor=TEXT_DARK,
        leading=10,
    )

    headers = ["#", "Model", "Date", "ID", "Model Card"] + [
        (f'{col["task_name"]} - {col["title"]}' if col["task_name"] else col["title"])
        for col in columns
    ]

    rows = [[Paragraph(_xml_escape(h), header_style) for h in headers]]
    submissions = leaderboard_payload.get("submissions") or []
    for idx, submission in enumerate(submissions, start=1):
        row = [
            idx,
            submission.get("model_name") or "Model",
            _format_date(submission.get("created_when")),
            submission.get("id", ""),
            "Yes" if submission.get("has_model_card") else "-",
        ]
        for column in columns:
            row.append(_score_for_column(submission, column))
        rows.append([_cell(value) for value in row])

    if len(headers) <= 5:
        col_widths = [1.0 * cm, 5.0 * cm, 3.2 * cm, 1.3 * cm, 2.0 * cm]
    else:
        fixed = [1.0 * cm, 4.8 * cm, 3.1 * cm, 1.2 * cm, 1.8 * cm]
        remaining = max(doc.width - sum(fixed), 1)
        metric_width = remaining / max(len(headers) - len(fixed), 1)
        col_widths = fixed + [metric_width] * (len(headers) - len(fixed))

    table = LongTable(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("ALIGN", (4, 1), (4, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd8dc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_EVEN]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        styles["meta"],
    ))

    doc.build(story)
    return buf.getvalue()

"""
Unified model card parser.

Supports four input modes:
    1. PDF file      (.pdf)              — text extraction via pypdf / PyPDF2
    2. JSON file     (.json)             — direct field mapping
    3. Markdown file (.md / .markdown)  — section-based extraction
    4. Form data     (dict)             — direct field mapping from in-page form

All parsers return a result dict with the following keys:
    model_name      – extracted model name string, or None on failure
    parsed_json     – structured dict with all required fields, or None on failure
    failure_reasons – list of human-readable strings; empty on success

Backward-compatibility shims at the bottom keep the old
``extract_model_card_metadata`` / ``extract_model_card_metadata_debug``
call signatures working when imported from this module.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

MODEL_CARD_OVERVIEW_PROMPT = (
    "Briefly describe the purpose of the model and the problem it is designed to solve."
)

REQUIRED_FIELDS = ["model_name", "task", "output", "overview"]

OPTIONAL_SECTION_HEADINGS = [
    "Data",
    "Model",
    "Evaluation",
    "Interpretability",
    "Limitations",
    "Intended Use",
    "Author",
]

PLACEHOLDER_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "tbd",
    "todo",
    "unknown",
}

ACCEPTED_EXTENSIONS = frozenset({".pdf", ".json", ".md", ".markdown"})


# ---------------------------------------------------------------------------
# Shared helper functions
# ---------------------------------------------------------------------------

def _has_meaningful_value(value):
    if not value:
        return False
    normalized = " ".join(str(value).split()).strip().lower().rstrip(".")
    if normalized in PLACEHOLDER_VALUES:
        return False
    if normalized.startswith("briefly describe the purpose of the model"):
        return False
    return True


def _extract_section(text, heading, next_headings):
    heading_pattern = re.escape(heading)
    next_heading_pattern = "|".join(re.escape(h) for h in next_headings)
    match = re.search(
        rf"{heading_pattern}\s*(?P<section>.*?)(?=^\s*(?:{next_heading_pattern})\s*$|\Z)",
        text,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group("section").strip()


def _extract_section_fallback(text, heading, next_headings):
    normalized = " ".join(text.split())
    heading_pattern = re.escape(heading)
    next_heading_pattern = "|".join(re.escape(h) for h in next_headings)
    match = re.search(
        rf"{heading_pattern}\s*(?P<section>.*?)(?=\s+(?:{next_heading_pattern})\b|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group("section").strip()


def _section_needs_fallback(section_text, next_headings):
    if not section_text:
        return True
    for heading in next_headings:
        if re.search(rf"\b{re.escape(heading)}\b", section_text, flags=re.IGNORECASE):
            return True
    return False


def _trim_field_value(candidate, stop_labels):
    trimmed = candidate.strip()
    if not trimmed:
        return ""
    stop_pattern = "|".join(rf"{label}\s*:" for label in stop_labels)
    match = re.search(
        rf"^(?P<value>.*?)(?=\s+(?:{stop_pattern})|$)", trimmed, flags=re.IGNORECASE
    )
    if not match:
        return trimmed
    return match.group("value").strip()


def _extract_info_fields(model_information):
    """Extract model_name / task / output from the Model Information section text."""
    extracted = {"model_name": "", "task": "", "output": ""}

    for raw_line in model_information.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(
            r"(model\s*name|task|output)\s*:\s*(.*)$", line, flags=re.IGNORECASE
        )
        if not match:
            continue
        label = re.sub(r"\s+", "_", match.group(1).strip().lower())
        stop_labels = ["model name", "task", "output"]
        stop_labels = [s for s in stop_labels if s.replace(" ", "_") != label]
        candidate = _trim_field_value(match.group(2), stop_labels)
        if not candidate or re.match(
            r"^(model\s*name|task|output)\s*:", candidate, flags=re.IGNORECASE
        ):
            extracted[label] = ""
            continue
        extracted[label] = candidate

    if all(extracted.values()):
        return extracted

    # Single-line fallback (all fields on one line)
    normalized = " ".join(model_information.split())
    field_patterns = {
        "model_name": r"model\s*name\s*:\s*(?P<value>.*?)(?=\s+task\s*:|\s+output\s*:|\s+overview\b|$)",
        "task": r"task\s*:\s*(?P<value>.*?)(?=\s+output\s*:|\s+overview\b|$)",
        "output": r"output\s*:\s*(?P<value>.*?)(?=\s+overview\b|$)",
    }
    for field_name, pattern in field_patterns.items():
        if extracted[field_name]:
            continue
        m = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = m.group("value").strip()
        if not candidate or re.match(
            r"^(model\s*name|task|output)\s*:", candidate, flags=re.IGNORECASE
        ):
            continue
        extracted[field_name] = candidate

    return extracted


def _clean_overview(overview):
    cleaned = overview.strip()
    if not cleaned:
        return ""
    prompt_pattern = re.escape(MODEL_CARD_OVERVIEW_PROMPT)
    cleaned = re.sub(prompt_pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fail(reasons):
    return {"model_name": None, "parsed_json": None, "failure_reasons": list(reasons)}


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------

def parse_model_card_pdf(uploaded_file):
    """
    Parse a PDF model card.

    Returns:
        dict with keys: model_name, parsed_json, failure_reasons
                        (plus extracted_text_preview for debug logging).
    """
    if not uploaded_file:
        result = _fail(["missing file"])
        result["extracted_text_preview"] = ""
        return result

    reader_cls = None
    try:
        from pypdf import PdfReader as reader_cls  # type: ignore[assignment]
    except Exception:
        try:
            from PyPDF2 import PdfReader as reader_cls  # type: ignore[assignment]
        except Exception:
            reader_cls = None

    if reader_cls is None:
        result = _fail(["pdf reader unavailable"])
        result["extracted_text_preview"] = ""
        return result

    try:
        uploaded_file.seek(0)
        reader = reader_cls(uploaded_file)

        pages_text = []
        for page in reader.pages[:2]:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                continue
        full_text = "\n".join(pages_text)
        extracted_text_preview = full_text[:2000]

        model_information = _extract_section(
            full_text, "Model Information", ["Overview"]
        )
        if _section_needs_fallback(model_information, ["Overview"]):
            model_information = _extract_section_fallback(
                full_text, "Model Information", ["Overview"]
            )

        overview = _extract_section(
            full_text, "Overview", OPTIONAL_SECTION_HEADINGS
        )
        if _section_needs_fallback(overview, OPTIONAL_SECTION_HEADINGS):
            overview = _extract_section_fallback(
                full_text, "Overview", OPTIONAL_SECTION_HEADINGS
            )

        info_fields = _extract_info_fields(model_information)
        overview_content = _clean_overview(overview)

        failure_reasons = []
        if not _has_meaningful_value(model_information):
            failure_reasons.append('missing "Model Information" section')
        if not _has_meaningful_value(info_fields["model_name"]):
            failure_reasons.append('missing "Model Name" value')
        if not _has_meaningful_value(info_fields["task"]):
            failure_reasons.append('missing "Task" value')
        if not _has_meaningful_value(info_fields["output"]):
            failure_reasons.append('missing "Output" value')
        if not _has_meaningful_value(overview_content):
            failure_reasons.append('missing meaningful "Overview" content')

        uploaded_file.seek(0)

        if failure_reasons:
            return {
                "model_name": None,
                "parsed_json": None,
                "failure_reasons": failure_reasons,
                "extracted_text_preview": extracted_text_preview,
            }

        parsed_json = {
            "source_format": "pdf",
            "extracted_text_preview": extracted_text_preview,
            "model_information": model_information,
            "model_name": info_fields["model_name"],
            "task": info_fields["task"],
            "output": info_fields["output"],
            "overview": overview_content,
        }
        return {
            "model_name": info_fields["model_name"],
            "parsed_json": parsed_json,
            "failure_reasons": [],
            "extracted_text_preview": extracted_text_preview,
        }

    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        result = _fail(["pdf text extraction failed"])
        result["extracted_text_preview"] = ""
        return result


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def parse_model_card_json(uploaded_file):
    """
    Parse a JSON model card file.

    Expected structure::

        {
            "model_name": "...",
            "task": "...",
            "output": "...",
            "overview": "..."
        }

    Returns:
        dict with keys: model_name, parsed_json, failure_reasons
    """
    if not uploaded_file:
        return _fail(["missing file"])

    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text)
    except Exception as exc:
        return _fail([f"invalid JSON: {exc}"])
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    if not isinstance(data, dict):
        return _fail(["JSON root must be an object/dict"])

    failure_reasons = []
    for field in REQUIRED_FIELDS:
        if not _has_meaningful_value(data.get(field, "")):
            failure_reasons.append(f'missing or placeholder "{field}" value')

    if failure_reasons:
        return _fail(failure_reasons)

    parsed_json = {
        "source_format": "json",
        "model_name": str(data["model_name"]).strip(),
        "task": str(data["task"]).strip(),
        "output": str(data["output"]).strip(),
        "overview": str(data["overview"]).strip(),
    }
    # Preserve any extra optional keys the participant included
    for key, value in data.items():
        if key not in parsed_json:
            parsed_json[key] = value

    return {
        "model_name": parsed_json["model_name"],
        "parsed_json": parsed_json,
        "failure_reasons": [],
    }


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def parse_model_card_markdown(uploaded_file):
    """
    Parse a Markdown model card file.

    Expected structure mirrors the official template::

        # Model Information
        Model Name: ...
        Task: ...
        Output: ...

        # Overview
        ...

    Returns:
        dict with keys: model_name, parsed_json, failure_reasons
    """
    if not uploaded_file:
        return _fail(["missing file"])

    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    except Exception as exc:
        return _fail([f"could not read markdown file: {exc}"])
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    model_information = _extract_section(text, "Model Information", ["Overview"])
    if _section_needs_fallback(model_information, ["Overview"]):
        model_information = _extract_section_fallback(
            text, "Model Information", ["Overview"]
        )

    overview = _extract_section(text, "Overview", OPTIONAL_SECTION_HEADINGS)
    if _section_needs_fallback(overview, OPTIONAL_SECTION_HEADINGS):
        overview = _extract_section_fallback(
            text, "Overview", OPTIONAL_SECTION_HEADINGS
        )

    info_fields = _extract_info_fields(model_information)
    overview_content = _clean_overview(overview)

    failure_reasons = []
    if not _has_meaningful_value(info_fields["model_name"]):
        failure_reasons.append('missing "Model Name" value')
    if not _has_meaningful_value(info_fields["task"]):
        failure_reasons.append('missing "Task" value')
    if not _has_meaningful_value(info_fields["output"]):
        failure_reasons.append('missing "Output" value')
    if not _has_meaningful_value(overview_content):
        failure_reasons.append('missing meaningful "Overview" content')

    if failure_reasons:
        return _fail(failure_reasons)

    parsed_json = {
        "source_format": "markdown",
        "model_information": model_information,
        "model_name": info_fields["model_name"],
        "task": info_fields["task"],
        "output": info_fields["output"],
        "overview": overview_content,
    }
    return {
        "model_name": info_fields["model_name"],
        "parsed_json": parsed_json,
        "failure_reasons": [],
    }


# ---------------------------------------------------------------------------
# Form-data parser
# ---------------------------------------------------------------------------

def parse_model_card_form_data(data_dict):
    """
    Parse model card from a plain dict submitted via the in-page form.

    Expected keys: ``model_name``, ``task``, ``output``, ``overview``.

    Returns:
        dict with keys: model_name, parsed_json, failure_reasons
    """
    if not data_dict:
        return _fail(["empty form data"])

    failure_reasons = []
    for field in REQUIRED_FIELDS:
        if not _has_meaningful_value(data_dict.get(field, "")):
            failure_reasons.append(f'missing or placeholder "{field}" value')

    if failure_reasons:
        return _fail(failure_reasons)

    parsed_json = {
        "source_format": "form",
        "model_name": str(data_dict["model_name"]).strip(),
        "task": str(data_dict["task"]).strip(),
        "output": str(data_dict["output"]).strip(),
        "overview": str(data_dict["overview"]).strip(),
    }
    return {
        "model_name": parsed_json["model_name"],
        "parsed_json": parsed_json,
        "failure_reasons": [],
    }


# ---------------------------------------------------------------------------
# Unified dispatch
# ---------------------------------------------------------------------------

def parse_model_card(uploaded_file, filename=""):
    """
    Dispatch to the appropriate parser based on *filename*'s extension.

    Returns:
        dict with keys: model_name, parsed_json, failure_reasons
    """
    ext = ""
    if filename:
        parts = filename.rsplit(".", 1)
        if len(parts) == 2:
            ext = "." + parts[1].lower()

    if ext == ".pdf":
        return parse_model_card_pdf(uploaded_file)
    elif ext == ".json":
        return parse_model_card_json(uploaded_file)
    elif ext in (".md", ".markdown"):
        return parse_model_card_markdown(uploaded_file)
    else:
        return _fail(
            [
                f"unsupported model card file type '{ext}'; "
                f"accepted: .pdf, .json, .md, .markdown"
            ]
        )


# ---------------------------------------------------------------------------
# Backward-compatibility shims
# (previously defined directly in api.serializers.submissions)
# ---------------------------------------------------------------------------

def extract_model_card_metadata_debug(uploaded_file):
    """
    Drop-in replacement for the old function of the same name.
    Delegates to ``parse_model_card_pdf`` and ensures the
    ``extracted_text_preview`` key is always present.
    """
    result = parse_model_card_pdf(uploaded_file)
    result.setdefault("extracted_text_preview", "")
    return result


def extract_model_card_metadata(uploaded_file):
    """
    Drop-in replacement for the old function of the same name.
    Returns ``(model_name, parsed_json)``.
    """
    debug = extract_model_card_metadata_debug(uploaded_file)
    return debug["model_name"], debug["parsed_json"]

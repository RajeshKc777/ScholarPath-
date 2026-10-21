"""Field extraction from document text, verified against the source.

The model proposes values; this module *verifies* them. A proposed value is
accepted only when it (or its digits, for numbers) literally appears in the
document text, and the user confirms it. Nothing unverifiable is saved - the
honesty rules from goals.md section 2 apply here with full force.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from scholarpath.gateway.base import (
    ChatRequest,
    GatewayError,
    GatewayProtocolError,
    Message,
    ModelGateway,
)

EXTRACTABLE_FIELDS = (
    "student_name",
    "degree_level",
    "discipline",
    "institution",
    "graduation_year",
    "gpa",
    "nationality",
    "ielts",
    "toefl",
    "preferred_countries",
    "funding_need",
)

FIELD_LABELS = {
    "student_name": "Student name",
    "degree_level": "Degree level",
    "discipline": "Discipline",
    "institution": "Institution",
    "graduation_year": "Graduation year",
    "gpa": "GPA",
    "nationality": "Nationality",
    "ielts": "IELTS overall",
    "toefl": "TOEFL overall",
    "preferred_countries": "Preferred countries",
    "funding_need": "Funding needed",
}

_INSTRUCTIONS = """Extract academic facts from the document text below.

Respond with ONE JSON object and nothing else:
{{"fields": {{"<field>": "<exact value from the text>" or null, ...}}}}

Fields (use exactly these keys): {fields}

Hard rules:
- A value must be copied word-for-word (or digit-for-digit) from the text.
- If a fact is not clearly in the text, its value MUST be null. Never infer,
  convert, complete, or guess.
- Numbers keep their digits exactly as printed (3.62 stays 3.62, not 3.62/4).
"""

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True, slots=True)
class DraftField:
    """One proposed value with verification state, ready for user confirmation."""

    name: str
    value: str          # may be "" = unknown
    verified: bool      # appears verbatim in the source text
    rejected_reason: str = ""


@dataclass(frozen=True, slots=True)
class ProfileDraft:
    filename: str
    fields: tuple[DraftField, ...] = field(default_factory=tuple)
    warnings: list[str] = field(default_factory=list)


def build_prompt(text: str) -> str:
    return (
        _INSTRUCTIONS.format(fields=", ".join(EXTRACTABLE_FIELDS))
        + "\n\nDocument text:\n<<<BEGIN>>>\n"
        + text.strip()
        + "\n<<<END>>>"
    )


def _whole_tokens(value: str) -> list[str]:
    return re.findall(r"[\w'-]+", value.lower())


# -- normalisation (tolerant, but never inventing) -------------------------

_QUOTE_MAP = {
    ord("‘"): "'", ord("’"): "'", ord("‚"): "'", ord("‛"): "'",
    ord("“"): '"', ord("”"): '"', ord("„"): '"', ord("‟"): '"',
    ord("′"): "'", ord("″"): '"', ord("‹"): "'", ord("›"): "'",
}
_DASH_MAP = {
    ord("‐"): "-", ord("‑"): "-", ord("‒"): "-", ord("–"): "-",
    ord("—"): "-", ord("−"): "-", ord("﹘"): "-", ord("﹣"): "-",
}
# A word broken across a line by a hyphen ("exam-\nple" -> "example").
_HYPHEN_BREAK_RE = re.compile(r"(\w)[-‐‑‒–—]\s*\n\s*(\w)")
_WHITESPACE_RE = re.compile(r"\s+")
_ORDINAL_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _normalize(text: str) -> str:
    """The text as a reader would hear it: one spelling, one spacing.

    NFKC folds the unicode variants (full-width digits, ligatures), quote and
    dash styles are unified, words split by a hyphen at a line break are
    joined, and all whitespace becomes a single space. Nothing is added and
    nothing is dropped - only the differences that no reader would notice.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = out.translate(_QUOTE_MAP).translate(_DASH_MAP)
    out = _HYPHEN_BREAK_RE.sub(r"\1\2", out)
    out = _WHITESPACE_RE.sub(" ", out)
    return out.strip()


# -- dates -----------------------------------------------------------------

def date_parts(text: str) -> tuple[int | None, int | None, int | None] | None:
    """(year, month, day) for a date-like string, or None when it is not one.

    A numeric date whose day and month could both be <= 12 is ambiguous
    (05/11/2025) and is deliberately not parsed: guessing would not be honest.
    """
    return _date_parts(text)


def _date_parts(text: str) -> tuple[int | None, int | None, int | None] | None:
    """(year, month, day) for a date-like string, or None when it is not one.

    A numeric date whose day and month could both be <= 12 is ambiguous
    (05/11/2025) and is deliberately not parsed: guessing would not be honest.
    """
    cleaned = _ORDINAL_RE.sub(r"\1", text.strip().rstrip("."))
    if not cleaned:
        return None

    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (year, month, day)
        return None

    numeric = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", cleaned)
    if numeric:
        first, second, year = (int(part) for part in numeric.groups())
        if first > 12 and second <= 12:
            return (year, second, first)
        if second > 12 and first <= 12:
            return (year, first, second)
        return None

    day_month = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?(?:\s+(\d{4}))?", cleaned)
    if day_month:
        month = _MONTHS.get(day_month.group(2).casefold())
        if month:
            year = int(day_month.group(3)) if day_month.group(3) else None
            return (year, month, int(day_month.group(1)))

    month_day = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:,)?(?:\s+(\d{4}))?", cleaned)
    if month_day:
        month = _MONTHS.get(month_day.group(1).casefold())
        if month:
            year = int(month_day.group(3)) if month_day.group(3) else None
            return (year, month, int(month_day.group(2)))

    return None


def _dates_in(text: str) -> list[tuple[int | None, int | None, int | None]]:
    """Every date-like phrase in the text, as (year, month, day)."""
    found: list[tuple[int | None, int | None, int | None]] = []
    pattern = re.compile(
        r"\d{4}-\d{1,2}-\d{1,2}"
        r"|\d{1,2}[/-]\d{1,2}[/-]\d{4}"
        r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?(?:\s+\d{4})?"
        r"|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?(?:\s+\d{4})?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        parts = _date_parts(match.group(0))
        if parts is not None:
            found.append(parts)
    return found


def _same_date(
    value_parts: tuple[int | None, int | None, int | None],
    source_parts: tuple[int | None, int | None, int | None],
) -> bool:
    """True when both describe the same day, with nothing added by the value."""
    for index, name in enumerate(("year", "month", "day")):
        mine = value_parts[index]
        theirs = source_parts[index]
        if mine is None:
            continue
        if theirs is None:
            return False  # the value states a part the page does not
        if mine != theirs:
            return False
    return True


def verbatim_in_source(value: str, source_text: str) -> bool:
    """Is this value really on the page, as a reader would see it?

    Both sides are normalised first (unicode, quotes, dashes, hyphenated line
    breaks, spacing), so "Deadline: 5th November 2025" verifies against
    "Deadline: 5 November 2025" and "Chevening's" against "Chevening’s".
    Dates are compared by value, not by spelling. Nothing is accepted that is
    not in the source after that normalisation.
    """
    source = _normalize(source_text)
    cleaned = _normalize(value)
    if not cleaned:
        return False
    source_lower = source.casefold()
    cleaned_lower = cleaned.casefold()

    # literal containment, but never inside a larger word ("Nepal" vs "Nepali")
    if re.search(r"(?<!\w)" + re.escape(cleaned_lower) + r"(?!\w)", source_lower):
        return True

    # a date verifies by value, not by spelling
    value_date = _date_parts(cleaned)
    if value_date is not None:
        for source_date in _dates_in(source):
            if _same_date(value_date, source_date):
                return True

    tokens = _whole_tokens(cleaned_lower)
    source_tokens = set(_whole_tokens(source_lower))
    has_letters = any(character.isalpha() for character in cleaned)
    if tokens and all(token in source_tokens for token in tokens):
        if any(ch.isdigit() for ch in cleaned):
            return _digits_match(cleaned, source_lower)
        return True

    if any(ch.isdigit() for ch in cleaned) and not has_letters:
        # Only a purely numeric value may verify on its digits alone: a value
        # that also names something ("December 2025") must have every word on
        # the page, so a year that appears elsewhere cannot carry it.
        return _digits_match(cleaned, source_lower)
    return False


def _digits_match(value: str, source_lower: str) -> bool:
    """Every digit group of the value appears, in order, with numeric bounds.

    The matched span must carry exactly the value's digit groups, so "1 2"
    never matches a source that merely contains "12".
    """
    groups = re.findall(r"\d+", value)
    if not groups:
        return False
    pattern = r"(?<!\d)" + r"\D*?".join(re.escape(g) for g in groups) + r"(?!\d)"
    match = re.search(pattern, source_lower)
    if match is None:
        return False
    return re.findall(r"\d+", match.group(0)) == groups


def parse_model_json(
    raw: str, allowed: frozenset[str] | tuple[str, ...] | None = None
) -> dict[str, str | None]:
    """Parse the model's JSON reply; raise on any unusable shape.

    `allowed` restricts accepted field names (defaults to profile fields);
    the scholarship pipeline passes its own set.
    """
    accepted = allowed if allowed is not None else EXTRACTABLE_FIELDS
    match = _JSON_BLOCK.search(raw)
    if match is None:
        raise GatewayProtocolError("The model did not return JSON I could parse.")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise GatewayProtocolError(
            f"The model returned malformed JSON ({exc})."
        ) from exc
    fields = payload.get("fields") if isinstance(payload, dict) else None
    if not isinstance(fields, dict):
        raise GatewayProtocolError(
            "The model's JSON is missing the \"fields\" object."
        )
    parsed: dict[str, str | None] = {}
    for name, value in fields.items():
        if name not in accepted:
            continue
        if value is None:
            parsed[name] = None
        elif isinstance(value, str):
            parsed[name] = value.strip()
        elif isinstance(value, int | float):
            parsed[name] = str(value)
        else:
            parsed[name] = None
    if not parsed:
        raise GatewayProtocolError(
            "The model returned no fields this build recognises."
        )
    return parsed


def build_draft(
    filename: str,
    source_text: str,
    proposed: dict[str, str | None],
) -> ProfileDraft:
    """Verify every proposed value against the document text."""
    fields: list[DraftField] = []
    warnings: list[str] = []
    for name in EXTRACTABLE_FIELDS:
        value = proposed.get(name)
        if value is None or not value.strip():
            continue
        verified = verbatim_in_source(value.strip(), source_text)
        fields.append(
            DraftField(
                name=name,
                value=value.strip(),
                verified=verified,
                rejected_reason="" if verified else "not found word-for-word in the document",
            )
        )
    hidden = sorted(set(proposed) - set(EXTRACTABLE_FIELDS))
    if hidden:
        warnings.append(
            "Ignored the model's unsupported fields: " + ", ".join(hidden) + "."
        )
    return ProfileDraft(filename=filename, fields=tuple(fields), warnings=warnings)


def extract_fields(
    gateway: ModelGateway, text: str, model: str | None = None
) -> dict[str, str | None]:
    """One gateway call; the caller owns threading (UI stays responsive)."""
    request = ChatRequest(
        messages=[Message(role="user", content=build_prompt(text))],
        model=model,
    )
    response = gateway.complete(request)
    return parse_model_json(response.text)

"""Field extraction from document text, verified against the source.

The model proposes values; this module *verifies* them. A proposed value is
accepted only when it (or its digits, for numbers) literally appears in the
document text, and the user confirms it. Nothing unverifiable is saved - the
honesty rules from goals.md section 2 apply here with full force.
"""

from __future__ import annotations

import json
import re
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


def verbatim_in_source(value: str, source_text: str) -> bool:
    """Case- and whitespace-insensitive containment, or exact word tokens.

    Numbers verify through a digit-group pattern so separator variants
    ("3.62/4" vs "3.62 / 4.00") still count, but a digit inside a larger
    number never does ("105" does not match "1050").
    """
    source_lower = " ".join(source_text.lower().split())
    cleaned = " ".join(value.split()).lower()
    if not cleaned:
        return False
    # literal containment, but never inside a larger word ("Nepal" vs "Nepali")
    if re.search(r"(?<!\w)" + re.escape(cleaned) + r"(?!\w)", source_lower):
        return True

    tokens = _whole_tokens(value)
    source_tokens = set(_whole_tokens(source_lower))
    if tokens and all(token in source_tokens for token in tokens):
        if any(ch.isdigit() for ch in value):
            return _digits_match(value, source_lower)
        return True

    if any(ch.isdigit() for ch in value):
        return _digits_match(value, source_lower)
    return False


def _digits_match(value: str, source_lower: str) -> bool:
    """Every digit group of the value appears, in order, with numeric bounds."""
    groups = re.findall(r"\d+", value)
    if not groups:
        return False
    pattern = r"(?<!\d)" + r"\D*?".join(re.escape(g) for g in groups) + r"(?!\d)"
    return re.search(pattern, source_lower) is not None


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

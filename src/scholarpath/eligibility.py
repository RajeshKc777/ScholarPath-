"""Deterministic eligibility checks over a saved profile and a verified record.

Everything here is rule-based Python - no model, no probabilities, no guessing.
The scholarship side comes from page-verified values (verbatim page text); the
student side comes from the local profile. When either side does not state a
fact clearly, the requirement is reported as **unknown** or **needs manual
verification**, never assumed.

Requirement states (G107):
    satisfied        - both sides state the fact and they match
    not_satisfied    - both sides state the fact and they conflict
    unknown          - a side is silent; the page or the profile does not say
    manual           - the text is present but cannot be read mechanically

The overall verdict never says "you are eligible": it reports conflicts, gaps,
and open checks only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

SATISFIED = "satisfied"
NOT_SATISFIED = "not_satisfied"
UNKNOWN = "unknown"
MANUAL = "manual"

STATE_LABELS = {
    SATISFIED: "satisfied",
    NOT_SATISFIED: "not satisfied",
    UNKNOWN: "unknown",
    MANUAL: "needs checking",
}


@dataclass(frozen=True)
class RequirementResult:
    key: str
    label: str
    state: str
    explanation: str
    evidence: str = ""
    critical: bool = True


@dataclass(frozen=True)
class EligibilityReport:
    scholarship_id: int
    title: str
    source_url: str
    retrieved_at: str
    requirements: tuple[RequirementResult, ...]

    def state_of(self, key: str) -> str:
        for requirement in self.requirements:
            if requirement.key == key:
                return requirement.state
        return UNKNOWN

    def conflicts(self) -> tuple[RequirementResult, ...]:
        return tuple(r for r in self.requirements if r.state == NOT_SATISFIED)

    def open_checks(self) -> tuple[RequirementResult, ...]:
        return tuple(r for r in self.requirements if r.state in (UNKNOWN, MANUAL))

    def verdict(self) -> str:
        """Plain-language summary; never a probability, never 'you are eligible'."""
        conflicts = self.conflicts()
        if conflicts:
            return (
                "Conflicts with the page as written: "
                + "; ".join(r.label for r in conflicts)
            )
        open_checks = self.open_checks()
        if open_checks:
            return (
                f"Potential only \u2014 {len(open_checks)} requirement(s) need "
                "checking before anything can be called a match"
            )
        if all(r.state == SATISFIED for r in self.requirements):
            return (
                "No conflicts found on the checked requirements \u2014 "
                "confirm on the official page before applying"
            )
        return "Insufficient information to assess"

    def rank_key(self) -> tuple:
        """Deterministic ordering: fewer conflicts, fewer open checks, more wins."""
        return (
            len(self.conflicts()),
            len(self.open_checks()),
            -sum(1 for r in self.requirements if r.state == SATISFIED),
            self.title.casefold(),
            self.scholarship_id,
        )


# -- matching helpers ---------------------------------------------------------

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _words(text: str) -> set[str]:
    return {token.casefold() for token in _WORD_RE.findall(text)}


def _mentions(haystack: str, needle: str) -> bool:
    """Whole-word, case-insensitive presence (never inside a larger word)."""
    if not needle.strip():
        return False
    pattern = r"(?<!\w)" + re.escape(" ".join(needle.split())) + r"(?!\w)"
    return re.search(pattern, " ".join(haystack.split()), re.IGNORECASE) is not None


_DEGREE_WORDS = {
    "bachelor": ("bachelor", "bachelors", "bachelor's", "undergraduate"),
    "master": ("master", "masters", "master's", "postgraduate", "msc", "ma"),
    "phd": ("phd", "ph.d", "doctorate", "doctoral", "doctor"),
    "postdoc": ("postdoc", "postdoctoral"),
}


def _degree_level_of(text: str) -> str | None:
    lowered = text.casefold()
    for level, words in _DEGREE_WORDS.items():
        if any(_mentions(lowered, word) for word in words):
            return level
    return None


_NON_SPECIFIC = (
    "all countries", "all nationalities", "any country", "any nationality",
    "developing countries", "eligible countries", "see list", "various",
    "international students", "worldwide",
)


def _nationality_list(value: str) -> list[str]:
    """Split the page's nationality text into entries (lines/semicolons)."""
    parts = re.split(r"[;\n]+", value)
    return [part.strip() for part in parts if part.strip()]


# -- requirement checks -------------------------------------------------------


def check_nationality(profile: dict, values: dict, evidence: str) -> RequirementResult:
    label = "Nationality"
    page_value = values.get("eligible_nationalities", "").strip()
    student = profile.get("nationality", "").strip()
    if not page_value:
        return RequirementResult(
            "nationality", label, UNKNOWN,
            "The page does not state eligible nationalities.",
        )
    lowered = page_value.casefold()
    if any(phrase in lowered for phrase in _NON_SPECIFIC):
        return RequirementResult(
            "nationality", label, MANUAL,
            "The page describes eligible nationalities in general terms; "
            "check the official list.",
            page_value,
        )
    if not student:
        return RequirementResult(
            "nationality", label, UNKNOWN,
            "Your nationality is not set in your profile.",
            page_value,
        )
    entries = _nationality_list(page_value)
    for entry in entries:
        if entry.casefold() == student.casefold():
            return RequirementResult(
                "nationality", label, SATISFIED,
                f"The page lists {entry}.", entry,
            )
    # explicit list that does not contain the student's country
    return RequirementResult(
        "nationality", label, NOT_SATISFIED,
        f"The page's list does not include {student}.",
        page_value,
    )


def check_degree(profile: dict, values: dict, evidence: str) -> RequirementResult:
    label = "Degree level"
    page_value = values.get("degree_levels", "").strip()
    student_text = profile.get("degree_level", "").strip()
    if not page_value:
        return RequirementResult(
            "degree", label, UNKNOWN,
            "The page does not state which degree levels are eligible.",
        )
    student_level = _degree_level_of(student_text) if student_text else None
    page_level = _degree_level_of(page_value)
    if not student_text:
        return RequirementResult(
            "degree", label, UNKNOWN,
            "Your degree level is not set in your profile.", page_value,
        )
    if student_level is None:
        return RequirementResult(
            "degree", label, MANUAL,
            f"Your degree level ({student_text!r}) could not be read mechanically.",
            page_value,
        )
    if page_level is None:
        return RequirementResult(
            "degree", label, MANUAL,
            "The page's degree wording could not be read mechanically.", page_value,
        )
    if student_level == page_level or (
        student_level == "postdoc" and page_level == "phd"
    ):
        return RequirementResult(
            "degree", label, SATISFIED,
            f"The page covers {page_level} level.", page_value,
        )
    return RequirementResult(
        "degree", label, NOT_SATISFIED,
        f"The page targets {page_level}; your profile says {student_level}.",
        page_value,
    )


_IELTS_RE = re.compile(r"IELTS[^\d]{0,25}(\d(?:\.\d)?)", re.IGNORECASE)
_TOEFL_RE = re.compile(r"TOEFL[^\d]{0,30}(\d{2,3})", re.IGNORECASE)


def _number(text: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def check_language(profile: dict, values: dict, evidence: str) -> RequirementResult:
    label = "Language requirement"
    page_value = values.get("language_requirement", "").strip()
    if not page_value:
        return RequirementResult(
            "language", label, UNKNOWN,
            "The page does not state a language requirement.",
        )
    ielts_req = _IELTS_RE.search(page_value)
    toefl_req = _TOEFL_RE.search(page_value)
    if ielts_req is None and toefl_req is None:
        return RequirementResult(
            "language", label, MANUAL,
            "The page states a language requirement in a form this build cannot "
            "read as a threshold.", page_value,
        )

    ielts_have = _number(profile.get("ielts", ""))
    toefl_have = _number(profile.get("toefl", ""))

    outcomes: list[bool] = []
    details: list[str] = []
    if ielts_req is not None:
        threshold = float(ielts_req.group(1))
        details.append(f"IELTS {threshold:g} required")
        if ielts_have is not None:
            outcomes.append(ielts_have >= threshold)
    if toefl_req is not None:
        threshold = float(toefl_req.group(1))
        details.append(f"TOEFL {threshold:g} required")
        if toefl_have is not None:
            outcomes.append(toefl_have >= threshold)

    if not outcomes:
        return RequirementResult(
            "language", label, UNKNOWN,
            "You have not entered a matching test score in your profile. "
            + "; ".join(details), page_value,
        )
    if any(outcomes):
        return RequirementResult(
            "language", label, SATISFIED,
            "Your score meets the stated threshold. " + "; ".join(details),
            page_value,
        )
    if len(outcomes) == (ielts_req is not None) + (toefl_req is not None):
        return RequirementResult(
            "language", label, NOT_SATISFIED,
            "Your score is below the stated threshold. " + "; ".join(details),
            page_value,
        )
    return RequirementResult(
        "language", label, MANUAL,
        "One pathway is below the threshold and the other has no score in your "
        "profile. " + "; ".join(details), page_value,
    )


_GPA_RE = re.compile(r"GPA[^\d]{0,25}(\d+(?:\.\d+)?)(?:\s*(?:/|out of)\s*(\d+(?:\.\d+)?))?", re.IGNORECASE)


def _scale_of(text: str) -> str:
    """Normalise common scale wording to a comparable string."""
    value = text.strip().casefold()
    if not value or value == "unknown":
        return ""
    if "percent" in value:
        return "100"
    match = re.search(r"\d+(?:\.\d+)?", value)
    if match:
        number = float(match.group(0))
        return f"{number:g}"  # 4.0 -> "4", 4.5 -> "4.5"
    return value


def check_academic(profile: dict, values: dict, evidence: str) -> RequirementResult:
    label = "Academic requirement"
    page_value = values.get("academic_requirement", "").strip()
    if not page_value:
        return RequirementResult(
            "academic", label, UNKNOWN,
            "The page does not state an academic requirement.",
        )
    match = _GPA_RE.search(page_value)
    if match is None:
        return RequirementResult(
            "academic", label, MANUAL,
            "The page states an academic requirement that is not a readable GPA "
            "threshold.", page_value,
        )
    threshold = float(match.group(1))
    page_scale = _scale_of(match.group(2) or "")
    student_gpa = _number(profile.get("gpa", ""))
    student_scale = _scale_of(profile.get("gpa_scale", ""))
    if student_gpa is None:
        return RequirementResult(
            "academic", label, UNKNOWN,
            "No GPA is set in your profile.", page_value,
        )
    if not page_scale:
        return RequirementResult(
            "academic", label, MANUAL,
            f"The page requires GPA {threshold:g} but does not state its scale.",
            page_value,
        )
    if student_scale != page_scale:
        return RequirementResult(
            "academic", label, MANUAL,
            f"The page's GPA scale ({page_scale}) differs from your profile "
            f"({student_scale or 'not set'}); do not convert without a documented policy.",
            page_value,
        )
    if student_gpa >= threshold:
        return RequirementResult(
            "academic", label, SATISFIED,
            f"Your GPA {student_gpa:g} meets the stated {threshold:g} on the "
            f"same {page_scale}-point scale.", page_value,
        )
    return RequirementResult(
        "academic", label, NOT_SATISFIED,
        f"Your GPA {student_gpa:g} is below the stated {threshold:g} on the "
        f"{page_scale}-point scale.", page_value,
    )


_DATE_FORMATS = (
    "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%d %B, %Y", "%d %b, %Y",
)


def _parse_deadline(text: str) -> date | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def check_deadline(
    profile: dict, values: dict, evidence: str, today: date | None = None
) -> RequirementResult:
    label = "Deadline"
    page_value = values.get("deadline", "").strip()
    if not page_value:
        return RequirementResult(
            "deadline", label, UNKNOWN,
            "The page does not state a deadline.",
        )
    parsed = _parse_deadline(page_value)
    current = today or date.today()
    if parsed is None:
        return RequirementResult(
            "deadline", label, MANUAL,
            "The deadline was not in a date format this build reads; check the "
            "official page.", page_value,
        )
    if parsed < current:
        return RequirementResult(
            "deadline", label, NOT_SATISFIED,
            f"The stated deadline ({parsed.isoformat()}) has passed.", page_value,
        )
    return RequirementResult(
        "deadline", label, SATISFIED,
        f"The stated deadline ({parsed.isoformat()}) is still ahead.", page_value,
    )


# -- report assembly -----------------------------------------------------------


def evaluate(
    profile: dict,
    scholarship_row: dict,
    today: date | None = None,
) -> EligibilityReport:
    """Run every check for one stored scholarship record."""
    data = scholarship_row.get("data", {}) if isinstance(scholarship_row, dict) else {}
    values: dict[str, str] = data.get("values", {}) if isinstance(data, dict) else {}
    checks = (
        check_nationality(profile, values, ""),
        check_degree(profile, values, ""),
        check_language(profile, values, ""),
        check_academic(profile, values, ""),
        check_deadline(profile, values, "", today=today),
    )
    return EligibilityReport(
        scholarship_id=int(scholarship_row.get("id", 0)),
        title=scholarship_row.get("title") or "(untitled record)",
        source_url=scholarship_row.get("final_url")
        or scholarship_row.get("requested_url", ""),
        retrieved_at=scholarship_row.get("retrieved_at", ""),
        requirements=tuple(checks),
    )


def evaluate_all(
    profile: dict, rows: Iterable[dict], today: date | None = None
) -> list[EligibilityReport]:
    """Evaluate every stored record, deterministically ordered (best first)."""
    reports = [evaluate(profile, row, today=today) for row in rows]
    return sorted(reports, key=EligibilityReport.rank_key)

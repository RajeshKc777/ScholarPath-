"""Student profile: typed data, locally persisted, nothing invented.

Every field is optional - "unknown" is always a valid state, and the UI must
show what is genuinely known instead of filling gaps. Ingested documents feed
the profile only field-by-field, with explicit user confirmation (M3).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
DegreeLevel = Literal[
    "bachelor", "master", "phd", "postdoc", "other"
]
GpaScale = Literal["4.0", "5.0", "10", "percentage", "unknown"]

PROFILE_FIELDS = (
    ("student_name", "Student name"),
    ("degree_level", "Current degree"),
    ("discipline", "Discipline"),
    ("institution", "Institution"),
    ("graduation_year", "Graduation year"),
    ("gpa", "GPA"),
    ("gpa_scale", "GPA scale"),
    ("nationality", "Nationality"),
    ("ielts", "IELTS overall"),
    ("toefl", "TOEFL"),
    ("preferred_countries", "Preferred countries"),
    ("funding_need", "Funding needed"),
)


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_name: str = ""
    degree_level: str = ""          # DegreeLevel, empty = unknown (free text entry)
    discipline: str = ""
    institution: str = ""
    graduation_year: str = ""       # digits; validated on save
    gpa: str = ""                   # decimal string; validated on save
    gpa_scale: str = ""             # GpaScale, empty = unknown
    nationality: str = ""
    ielts: str = ""
    toefl: str = ""
    preferred_countries: str = ""   # comma-separated free text
    funding_need: str = ""
    updated_at: str = ""

    def filled_fields(self) -> list[str]:
        return [
            name for name, _label in PROFILE_FIELDS
            if str(getattr(self, name, "")).strip()
        ]

    def completion(self) -> int:
        """Percentage of profile fields that carry a value."""
        total = len(PROFILE_FIELDS)
        if total == 0:
            return 0
        return round(100 * len(self.filled_fields()) / total)

    def as_payload(self) -> dict[str, Any]:
        """Persistable dict (without the bookkeeping timestamps)."""
        payload = json.loads(self.model_dump_json())
        payload.pop("updated_at", None)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> tuple["Profile", list[str]]:
        """Load strict data, keeping only fields the current schema still accepts.

        Returns the profile plus dropped-field warnings (names only, never
        content) - configuration or code versions may disagree silently.
        """
        accepted: dict[str, str] = {}
        dropped: list[str] = []
        for name, _label in PROFILE_FIELDS:
            if name not in payload:
                continue
            value = payload[name]
            if not isinstance(value, str):
                dropped.append(name)
                continue
            try:
                cls.model_validate({name: value})
                accepted[name] = value
            except ValidationError:
                dropped.append(name)
        return cls(**accepted), dropped


def merge_confirmed(profile: Profile, confirmed: dict[str, str | None]) -> Profile:
    """Apply user-confirmed extraction fields onto the profile.

    Only fields in PROFILE_FIELDS are accepted; None leaves the field as-is
    (never wipes known data from a rejected guess).
    """
    data = profile.as_payload()
    for name, value in confirmed.items():
        if name not in {field for field, _ in PROFILE_FIELDS}:
            continue
        if value is None:
            continue
        cleaned = str(value).strip()
        if not cleaned:
            continue
        data[name] = cleaned
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return Profile.model_validate(data)

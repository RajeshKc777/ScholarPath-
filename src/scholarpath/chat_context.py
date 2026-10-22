"""What the chat may know before it answers (G181-G183).

The chat must not ask the student for facts the app already holds. The saved
profile is turned into a **compact summary** that names only the fields the
owner listed: degree level, GPA and its scale, nationality, preferred
countries, funding need and language scores. The student's name and the
documents are **never** part of it - only the fields below are read.

The summary travels with the chat message to the model service, so Settings
discloses it and a switch (`privacy.chat_profile`) turns it off. With the
switch off the chat is given nothing.
"""

from __future__ import annotations

from typing import Any

#: How each degree level in the profile is worded for the model.
DEGREE_WORDS = {
    "bachelor": "Bachelor graduate (a bachelor's degree is completed)",
    "master": "Master applicant / graduate",
    "phd": "PhD scholar",
    "postdoc": "Postdoc",
    "other": "Other",
}

#: The only profile fields that may leave the device with a chat message.
#: The name and the documents are not here, on purpose.
SUMMARY_FIELDS = (
    "degree_level",
    "gpa",
    "gpa_scale",
    "nationality",
    "preferred_countries",
    "funding_need",
    "ielts",
    "toefl",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def profile_summary(profile: dict | None) -> str:
    """The compact profile summary the chat is given ("" when there is none).

    Only the fields in `SUMMARY_FIELDS` are read, so a name, an institution
    or anything from a document can never end up in the summary.
    """
    if not profile:
        return ""
    parts: list[str] = []

    degree = _text(profile.get("degree_level"))
    if degree:
        parts.append(f"degree level: {DEGREE_WORDS.get(degree, degree)}")

    gpa = _text(profile.get("gpa"))
    if gpa:
        scale = _text(profile.get("gpa_scale"))
        if scale and scale != "unknown":
            parts.append(f"GPA: {gpa} (scale {scale})")
        else:
            parts.append(f"GPA: {gpa}")

    for key, label in (
        ("nationality", "nationality"),
        ("preferred_countries", "preferred countries"),
        ("funding_need", "funding need"),
    ):
        value = _text(profile.get(key))
        if value:
            parts.append(f"{label}: {value}")

    scores = [
        f"{label} {value}"
        for label, key in (("IELTS", "ielts"), ("TOEFL", "toefl"))
        if (value := _text(profile.get(key)))
    ]
    if scores:
        parts.append("language scores: " + ", ".join(scores))

    if not parts:
        return ""
    return (
        "Saved profile facts (already on this device, so never ask for them "
        "again): " + "; ".join(parts) + "."
    )

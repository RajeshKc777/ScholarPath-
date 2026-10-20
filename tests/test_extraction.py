"""M3 pipeline unit tests: verification of proposed values against the source."""

from __future__ import annotations

import pytest

from scholarpath.extraction import (
    ProfileDraft,
    DraftField,
    build_draft,
    build_prompt,
    parse_model_json,
)

SOURCE = """TRANSCRIPT - Bachelor of Science
Student: Ram Bahadur Thapa
GPA: 3.62 / 4.00   Graduation: 2024
Nationailty: Nepali IELTS: 6.5
Preferred countries: Germany, Netherlands
"""


def test_parse_accepts_a_valid_reply() -> None:
    parsed = parse_model_json(
        '{"fields": {"student_name": "Ram Bahadur Thapa", "gpa": 3.62, "rest": true}}'
    )
    assert parsed["student_name"] == "Ram Bahadur Thapa"
    assert parsed["gpa"] == "3.62"
    assert "rest" not in parsed  # unknown keys are dropped


def test_parse_nulls_survive() -> None:
    parsed = parse_model_json('{"fields": {"gpa": null}}')
    assert parsed == {"gpa": None}


def test_parse_rejects_non_json() -> None:
    from scholarpath.gateway.base import GatewayProtocolError

    with pytest.raises(GatewayProtocolError):
        parse_model_json("I'm sorry, I cannot extract that.")


def test_parse_rejects_missing_fields_object() -> None:
    from scholarpath.gateway.base import GatewayProtocolError

    with pytest.raises(GatewayProtocolError):
        parse_model_json("[]")
    with pytest.raises(GatewayProtocolError):
        parse_model_json('{"other": {}}')


def test_build_prompt_carries_the_hard_rules() -> None:
    prompt = build_prompt("Student: Ram\nGPA: 3.62")
    assert "MUST be null" in prompt
    assert "word-for-word" in prompt
    assert "Student: Ram" in prompt


def test_verified_values_pass() -> None:
    draft = build_draft(
        "t.pdf",
        SOURCE,
        {
            "student_name": "Ram Bahadur Thapa",
            "gpa": "3.62 / 4.00",
            "graduation_year": "2024",
            "ielts": "6.5",
            "nationality": "Nepali",
            "preferred_countries": "Germany, Netherlands",
        },
    )
    accepted = {f.name for f in draft.fields if f.verified}
    assert accepted == {
        "student_name", "gpa", "graduation_year", "ielts",
        "nationality", "preferred_countries",
    }


def test_a_value_spelled_differently_is_rejected() -> None:
    # The source says "Nepali". "Nepal"/"INDIAN" never appear as words.
    draft = build_draft("t.pdf", SOURCE, {"nationality": "Nepal", "toefl": "105"})
    by_name = {f.name: f for f in draft.fields}
    assert by_name["nationality"].verified is False
    assert by_name["toefl"].verified is False


def test_unverifiable_values_are_marked_unverified() -> None:
    draft = build_draft(
        "t.pdf",
        SOURCE,
        {
            "institution": "Tribhuvan University",   # not in the text at all
        },
    )
    institution = draft.fields[0]
    assert institution.verified is False
    assert "not found" in institution.rejected_reason


def test_empty_draft_when_nothing_proposed() -> None:
    draft = build_draft("t.pdf", SOURCE, {"gpa": None, "ielts": ""})
    assert draft.fields == ()


def test_draft_is_immutable_value_type() -> None:
    draft = build_draft("t.pdf", SOURCE, {"gpa": "3.62"})
    assert isinstance(draft, ProfileDraft)
    assert isinstance(draft.fields[0], DraftField)


def test_digits_match_across_separator_variants() -> None:
    draft = build_draft("t.pdf", SOURCE, {"gpa": "3.62/4"})
    assert draft.fields[0].verified

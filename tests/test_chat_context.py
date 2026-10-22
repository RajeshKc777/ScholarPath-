"""What the chat may know before it answers (G181).

The chat gets a compact summary of the saved profile so it stops asking for
facts the student already stored. The summary names only the listed fields -
never the name, never anything from a document - and a switch turns it off.
"""

from __future__ import annotations

from scholarpath.chat_context import profile_summary

PROFILE = {
    "student_name": "Rajesh Katuwal",
    "degree_level": "bachelor",
    "discipline": "Computer Science",
    "institution": "Kathmandu University",
    "graduation_year": "2024",
    "gpa": "3.6",
    "gpa_scale": "4.0",
    "nationality": "Nepal",
    "ielts": "7.0",
    "toefl": "",
    "preferred_countries": "Germany, Canada",
    "funding_need": "full funding",
}


def test_the_summary_holds_the_listed_facts() -> None:
    summary = profile_summary(PROFILE)

    assert "bachelor" in summary.casefold()
    assert "3.6" in summary
    assert "4.0" in summary
    assert "Nepal" in summary
    assert "Germany, Canada" in summary
    assert "full funding" in summary
    assert "IELTS 7.0" in summary


def test_the_summary_never_holds_the_name_or_other_fields() -> None:
    summary = profile_summary(PROFILE)

    assert "Rajesh" not in summary
    assert "Katuwal" not in summary
    assert "Kathmandu University" not in summary
    assert "Computer Science" not in summary
    assert "2024" not in summary


def test_an_empty_profile_gives_no_summary() -> None:
    assert profile_summary(None) == ""
    assert profile_summary({}) == ""
    assert profile_summary({"student_name": "Rajesh Katuwal"}) == ""


def test_the_summary_says_never_to_ask_again() -> None:
    summary = profile_summary(PROFILE)
    assert "never ask" in summary.casefold()


def test_an_unknown_scale_is_not_repeated() -> None:
    summary = profile_summary({"gpa": "85", "gpa_scale": "unknown"})
    assert "85" in summary
    assert "unknown" not in summary.casefold()

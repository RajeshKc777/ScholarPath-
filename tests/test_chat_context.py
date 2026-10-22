"""What the chat may know before it answers (G181).

The chat gets a compact summary of the saved profile so it stops asking for
facts the student already stored. The summary names only the listed fields -
never the name, never anything from a document - and a switch turns it off.
"""

from __future__ import annotations

from scholarpath.chat_context import (
    catalog_hits,
    catalog_message,
    content_words,
    profile_summary,
)

RECORD = {
    "id": 1,
    "title": "DAAD Development-Related Postgraduate Courses",
    "provider": "DAAD",
    "provider_domain": "daad.de",
    "level": "Master's",
    "countries": "Germany",
    "fields_of_study": "Development Studies",
    "funding_type": "Full funding",
    "amount_text": "EUR 1,000 per month",
    "deadline_text": "15 August",
    "deadline_date": "2027-08-15",
    "language_req": "English",
    "apply_url": "https://www.daad.de/en/apply",
    "final_url": "https://www.daad.de/en/graduate-scholarships",
    "retrieved_at": "2026-10-20T09:00:00+00:00",
    "data": {"last_checked_at": "2026-10-21T08:00:00+00:00"},
}

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


# -- the verified catalog (G182) -------------------------------------------------


def test_the_catalog_search_finds_the_record_a_message_names() -> None:
    hits = catalog_hits([RECORD], "is there a daad scholarship for germany?")

    assert len(hits) == 1
    assert hits[0].title.startswith("DAAD")


def test_the_catalog_block_cites_the_source_and_the_last_verified_date() -> None:
    block = catalog_message(catalog_hits([RECORD], "daad germany"))

    assert "https://www.daad.de/en/graduate-scholarships" in block
    assert "2026-10-21" in block
    assert "verified" in block.casefold()
    assert "unverified lead" in block.casefold()


def test_a_message_with_nothing_meaningful_finds_nothing() -> None:
    assert catalog_hits([RECORD], "hello there") == []


def test_the_words_that_carry_no_meaning_are_dropped() -> None:
    words = content_words("What scholarship programs are open for a master's in Germany?")
    assert "scholarship" not in words
    assert "programs" not in words
    assert "germany" in words
    assert "master's" in words


def test_records_that_match_more_words_come_first() -> None:
    other = dict(RECORD, id=2, title="Korea Scholarship", countries="Korea")
    hits = catalog_hits([RECORD, other], "germany scholarship")
    assert hits[0].record["id"] == 1

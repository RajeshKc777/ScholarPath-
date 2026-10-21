"""Verbatim verification: tolerant about spelling, strict about truth (G139)."""

from __future__ import annotations

from scholarpath.extraction import _normalize, verbatim_in_source

PAGE = (
    "Chevening Scholarships 2025\n"
    "Deadline: 5 November 2025. Host country: United Kingdom.\n"
    "Funded by the Chevening Trust — full tuition, GBP 1,200 per month.\n"
)


def test_plain_values_still_verify() -> None:
    assert verbatim_in_source("5 November 2025", PAGE)
    assert verbatim_in_source("United Kingdom", PAGE)


def test_unicode_width_is_normalised() -> None:
    assert verbatim_in_source("２０２５", "The year 2025 is printed.")


def test_quote_styles_are_normalised() -> None:
    assert verbatim_in_source("Chevening’s", "The Chevening's programme.")
    assert verbatim_in_source("Chevening's", "The Chevening’s programme.")


def test_dash_styles_are_normalised() -> None:
    assert verbatim_in_source("2025-2026", "The 2025 – 2026 cycle.")


def test_whitespace_differences_do_not_matter() -> None:
    assert verbatim_in_source("full tuition", PAGE)
    assert verbatim_in_source("  full   tuition  ", PAGE)
    assert verbatim_in_source("Host country: United Kingdom.", PAGE)


def test_a_word_broken_by_a_hyphen_at_a_line_break_is_one_word() -> None:
    source = "The exam-\nple closes on Friday."
    assert verbatim_in_source("example", source)
    assert not verbatim_in_source("examples", source)


def test_dates_verify_by_value_not_spelling() -> None:
    assert verbatim_in_source("5th November 2025", PAGE)
    assert verbatim_in_source("November 5, 2025", PAGE)
    assert verbatim_in_source("2025-11-05", PAGE)
    assert verbatim_in_source("5 November", PAGE)


def test_a_different_date_is_rejected() -> None:
    assert not verbatim_in_source("6 November 2025", PAGE)
    assert not verbatim_in_source("5 November 2026", PAGE)
    assert not verbatim_in_source("November 2024", PAGE)


def test_an_ambiguous_numeric_date_is_not_guessed() -> None:
    """05/11/2025 and 11/05/2025 cannot be compared, so nothing is claimed."""
    assert not verbatim_in_source("05/11/2025", "The date is 11/05/2025.")


def test_an_unambiguous_numeric_date_verifies() -> None:
    assert verbatim_in_source("25/12/2025", "Closes on 25 December 2025.")


def test_a_value_that_is_not_on_the_page_is_rejected() -> None:
    assert not verbatim_in_source("Paris", PAGE)
    assert not verbatim_in_source("scholarship", "Two scholarships are open.")
    assert not verbatim_in_source("December 2025", PAGE)


def test_digits_are_not_split_across_the_source() -> None:
    """'1 2' must not verify against a source that only contains '12'."""
    assert not verbatim_in_source("1 2", "The code is 12.")


def test_numbers_with_separator_variants_still_verify() -> None:
    assert verbatim_in_source("3.62/4", "GPA 3.62 / 4.00 on the transcript.")


def test_normalisation_never_adds_words() -> None:
    assert _normalize("Chevening’s  2025 – 2026") == "Chevening's 2025 - 2026"
    assert _normalize("") == ""

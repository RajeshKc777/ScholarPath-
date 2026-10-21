"""Search and filters over the catalog: text, level, country, deadline (G149).

The important behaviour is not "does LIKE work" - it is that a filter only
looks at the field it names, a level is matched from the page's own wording,
and a deadline is never guessed from an ambiguous string.
"""

from __future__ import annotations

from datetime import date

from scholarpath.search import (
    DEADLINE_ANY,
    DEADLINE_CLOSED,
    DEADLINE_OPEN,
    DEADLINE_SOON,
    DEADLINE_UNKNOWN,
    LEVEL_ANY,
    LEVEL_BACHELOR,
    LEVEL_MASTER,
    LEVEL_PHD,
    SearchFilters,
    deadline_phrase,
    deadline_state,
    level_matches,
    normalise_text,
    parsed_deadline,
    search_records,
    summary_line,
    text_matches,
    words_in,
)

TODAY = date(2026, 10, 21)


def record(**overrides) -> dict:
    base = {
        "id": 1,
        "title": "OPEN GRANT 2026",
        "provider": "Example Portal",
        "provider_domain": "example.gov",
        "institution": "Example University",
        "countries": "Netherlands",
        "level": "master's degrees",
        "fields_of_study": "economics, public policy",
        "funding_type": "fully funded tuition",
        "amount_text": "EUR 1 200",
        "deadline_text": "5 November 2026",
        "deadline_date": "2026-11-05",
        "language_req": "IELTS 6.5",
        "apply_url": "https://example.gov/open-grant/apply",
        "canonical_key": "example.gov|open grant 2026",
        "data": {"values": {}},
    }
    base.update(overrides)
    return base


# -- text ---------------------------------------------------------------------


def test_normalisation_folds_unicode_case_and_dash_style() -> None:
    assert normalise_text("  T\u00fcrkiye   Burslari ") == "turkiye burslari"
    assert normalise_text("Benefit \u2014 5\u20136 years") == "benefit - 5-6 years"
    assert normalise_text("\u201cChevening\u2019s\u201d") == '"chevening\'s"'


def test_words_are_whole_words() -> None:
    assert words_in("Master's (MSc), 2026") == ["master", "s", "msc", "2026"]


def test_a_text_search_looks_at_every_stored_field() -> None:
    row = record()
    for query in (
        "open grant",
        "example portal",
        "netherlands",
        "public policy",
        "fully funded",
        "5 november",
        "ielts",
        "example.gov",
    ):
        assert text_matches(row, query), query


def test_a_text_search_needs_every_word() -> None:
    row = record()
    assert text_matches(row, "master netherlands") is True
    assert text_matches(row, "master japan") is False


def test_a_text_search_ignores_case_and_spacing() -> None:
    assert text_matches(record(), "  OPEN   grant  ") is True


def test_a_text_search_folds_accents() -> None:
    row = record(title="T\u00fcrkiye Burslari")
    assert text_matches(row, "turkiye burslari") is True


def test_an_empty_query_matches_everything() -> None:
    assert text_matches(record(), "   ") is True


def test_a_word_is_not_found_inside_another_word() -> None:
    # "bachelor" must not match "Bacheloropolis" - matching is by whole word
    # for levels, while a free-text search is a plain substring by design.
    row = record(title="Bacheloropolis")
    assert text_matches(row, "bachelor") is True  # honest: the letters are there
    assert level_matches(row, LEVEL_BACHELOR) is False  # but it names no level


# -- level --------------------------------------------------------------------


def test_the_level_filter_reads_the_pages_own_wording() -> None:
    row = record(level="master's degrees")
    assert level_matches(row, LEVEL_MASTER) is True
    assert level_matches(row, LEVEL_BACHELOR) is False
    assert level_matches(row, LEVEL_PHD) is False
    assert level_matches(row, LEVEL_ANY) is True


def test_doctoral_wording_counts_as_phd() -> None:
    assert level_matches(record(level="doctoral programme"), LEVEL_PHD) is True
    assert level_matches(record(level="PhD studentships"), LEVEL_PHD) is True


def test_undergraduate_wording_counts_as_bachelor() -> None:
    assert level_matches(record(level="undergraduate degree"), LEVEL_BACHELOR) is True
    assert level_matches(record(level="BSc and MA"), LEVEL_BACHELOR) is True
    assert level_matches(record(level="BSc and MA"), LEVEL_MASTER) is True


def test_a_page_that_names_no_level_matches_no_level_filter() -> None:
    row = record(level="")
    assert level_matches(row, LEVEL_MASTER) is False
    assert level_matches(row, LEVEL_ANY) is True


# -- deadlines ----------------------------------------------------------------


def test_the_deadline_state_comes_from_the_stored_date_only() -> None:
    assert deadline_state(record(deadline_date="2026-11-05"), TODAY) == DEADLINE_SOON
    assert deadline_state(record(deadline_date="2027-06-01"), TODAY) == DEADLINE_OPEN
    assert deadline_state(record(deadline_date="2026-10-20"), TODAY) == DEADLINE_CLOSED
    assert deadline_state(record(deadline_date=""), TODAY) == DEADLINE_UNKNOWN
    assert deadline_state(record(deadline_date=None), TODAY) == DEADLINE_UNKNOWN


def test_an_ambiguous_deadline_stays_unknown() -> None:
    # The page said "05/11/2026" and the record kept only the text: no date.
    row = record(deadline_text="05/11/2026", deadline_date=None)
    assert parsed_deadline(row) is None
    assert deadline_state(row, TODAY) == DEADLINE_UNKNOWN


def test_an_unreadable_stored_date_does_not_crash() -> None:
    assert parsed_deadline(record(deadline_date="next spring")) is None
    assert deadline_state(record(deadline_date="next spring"), TODAY) == DEADLINE_UNKNOWN


def test_the_deadline_phrase_is_plain_and_honest() -> None:
    assert deadline_phrase(record(deadline_date="2026-11-05"), TODAY) == (
        "Closes in 15 days (2026-11-05)"
    )
    assert deadline_phrase(record(deadline_date="2026-10-21"), TODAY) == (
        "Closes today (2026-10-21)"
    )
    assert deadline_phrase(record(deadline_date="2026-10-22"), TODAY) == "Closes tomorrow"
    assert deadline_phrase(record(deadline_date="2026-10-01"), TODAY) == (
        "Closed on 2026-10-01"
    )
    assert deadline_phrase(record(deadline_date="2027-06-01"), TODAY) == (
        "Open until 2027-06-01 (223 days)"
    )
    assert deadline_phrase(record(deadline_date=""), TODAY) == (
        "No readable deadline date on the page"
    )


def test_the_deadline_filter_groups_are_honest() -> None:
    soon = record(deadline_date="2026-11-05")
    later = record(deadline_date="2027-06-01")
    closed = record(deadline_date="2026-10-20")
    unknown = record(deadline_date=None)

    def keep(row: dict, choice: str) -> bool:
        hits = search_records(
            [row], SearchFilters(deadline=choice), today=TODAY
        )
        return bool(hits)

    assert keep(soon, DEADLINE_OPEN) is True
    assert keep(later, DEADLINE_OPEN) is True
    assert keep(closed, DEADLINE_OPEN) is False
    assert keep(unknown, DEADLINE_OPEN) is False
    assert keep(soon, DEADLINE_SOON) is True
    assert keep(later, DEADLINE_SOON) is False
    assert keep(closed, DEADLINE_CLOSED) is True
    assert keep(unknown, DEADLINE_UNKNOWN) is True
    assert keep(unknown, DEADLINE_ANY) is True


# -- the field filters ---------------------------------------------------------


def test_the_country_filter_reads_only_the_country_field() -> None:
    row = record(title="Netherlands Grant", countries="Germany")
    hits = search_records([row], SearchFilters(country="Netherlands"), today=TODAY)
    assert hits == []


def test_the_country_filter_matches_a_part_of_the_stored_name() -> None:
    assert search_records(
        [record(countries="United Kingdom")], SearchFilters(country="kingdom"), TODAY
    )


def test_the_field_filter_reads_only_the_field_of_study() -> None:
    row = record(title="Economics Prize", fields_of_study="engineering")
    assert search_records([row], SearchFilters(field="economics"), TODAY) == []
    assert search_records([row], SearchFilters(field="engineering"), TODAY)


def test_the_provider_filter_reads_only_the_provider() -> None:
    row = record(title="Chevening Scholarships", provider="Example Portal")
    assert search_records([row], SearchFilters(provider="chevening"), TODAY) == []
    assert search_records([row], SearchFilters(provider="example"), TODAY)


def test_filters_combine() -> None:
    row = record()
    hits = search_records(
        [row],
        SearchFilters(
            text="grant",
            level=LEVEL_MASTER,
            country="netherlands",
            field="policy",
            provider="example",
            deadline=DEADLINE_OPEN,
        ),
        today=TODAY,
    )
    assert len(hits) == 1
    hits = search_records(
        [row], SearchFilters(text="grant", level=LEVEL_PHD), today=TODAY
    )
    assert hits == []


def test_any_set_reports_whether_anything_was_typed() -> None:
    assert SearchFilters().any_set() is False
    assert SearchFilters(text="  ").any_set() is False
    assert SearchFilters(level=LEVEL_ANY, deadline=DEADLINE_ANY).any_set() is False
    assert SearchFilters(text="grant").any_set() is True
    assert SearchFilters(level=LEVEL_PHD).any_set() is True
    assert SearchFilters(deadline=DEADLINE_SOON).any_set() is True


# -- order and summary ---------------------------------------------------------


def test_open_deadlines_come_first_then_undated_then_closed() -> None:
    rows = [
        record(id=1, title="Closed recently", deadline_date="2026-10-20"),
        record(id=2, title="No date", deadline_date=None),
        record(id=3, title="Open later", deadline_date="2027-06-01"),
        record(id=4, title="Closing soon", deadline_date="2026-11-01"),
        record(id=5, title="Closed long ago", deadline_date="2026-01-01"),
    ]
    hits = search_records(rows, SearchFilters(), today=TODAY)
    assert [hit.title for hit in hits] == [
        "Closing soon",
        "Open later",
        "No date",
        "Closed recently",
        "Closed long ago",
    ]


def test_the_same_list_always_orders_the_same_way() -> None:
    rows = [record(id=2, title="B", deadline_date="2027-01-01"),
            record(id=1, title="A", deadline_date="2027-01-01")]
    first = [hit.title for hit in search_records(rows, SearchFilters(), TODAY)]
    second = [hit.title for hit in search_records(list(reversed(rows)), SearchFilters(), TODAY)]
    assert first == second == ["A", "B"]


def test_the_summary_counts_records_and_open_deadlines() -> None:
    rows = [
        record(id=1, deadline_date="2026-10-20"),
        record(id=2, deadline_date="2026-11-05"),
        record(id=3, deadline_date=None),
    ]
    hits = search_records(rows, SearchFilters(), today=TODAY)
    assert summary_line(len(rows), hits) == (
        "3 of 3 record(s) match \u2014 1 with an open deadline."
    )
    assert summary_line(0, []) == "The catalog is empty."
    assert summary_line(3, []) == "No record matches these filters (3 in the catalog)."

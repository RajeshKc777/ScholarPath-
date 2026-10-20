"""Deterministic eligibility: conservative states, honest verdicts (Milestone 5)."""

from __future__ import annotations

from datetime import date

import pytest

from scholarpath.eligibility import (
    MANUAL,
    NOT_SATISFIED,
    SATISFIED,
    UNKNOWN,
    EligibilityReport,
    check_academic,
    check_deadline,
    check_degree,
    check_language,
    check_nationality,
    evaluate,
    evaluate_all,
)

TODAY = date(2026, 10, 20)


def profile(**overrides) -> dict:
    base = {
        "student_name": "Test Student",
        "nationality": "Nepal",
        "degree_level": "bachelor",
        "gpa": "3.62",
        "gpa_scale": "4.0",
        "ielts": "7.0",
        "toefl": "",
        "preferred_countries": "United Kingdom",
    }
    base.update(overrides)
    return base


def row(**values) -> dict:
    return {
        "id": 1,
        "title": values.get("title", "Test Scholarship"),
        "final_url": "https://example.edu/scholarship",
        "requested_url": "https://example.edu/scholarship",
        "retrieved_at": "2026-10-20T10:00:00",
        "data": {"values": {k: v for k, v in values.items() if k != "title"}},
    }


# -- nationality --------------------------------------------------------------

def test_nationality_listed_is_satisfied() -> None:
    result = check_nationality(
        profile(), {"eligible_nationalities": "India\nNepal\nBhutan"}, ""
    )
    assert result.state == SATISFIED
    assert "Nepal" in result.evidence


def test_nationality_explicitly_absent_is_not_satisfied() -> None:
    result = check_nationality(
        profile(nationality="Nepal"), {"eligible_nationalities": "India\nBhutan"}, ""
    )
    assert result.state == NOT_SATISFIED


def test_nationality_entry_must_be_whole_not_substring() -> None:
    result = check_nationality(
        profile(nationality="Nepali"), {"eligible_nationalities": "Nepal"}, ""
    )
    assert result.state == NOT_SATISFIED


def test_nationality_page_silent_is_unknown() -> None:
    assert check_nationality(profile(), {}, "").state == UNKNOWN


def test_nationality_profile_blank_is_unknown_even_if_page_lists() -> None:
    result = check_nationality(
        profile(nationality=""), {"eligible_nationalities": "India\nNepal"}, ""
    )
    assert result.state == UNKNOWN


def test_nationality_general_wording_is_manual() -> None:
    result = check_nationality(
        profile(), {"eligible_nationalities": "Developing countries only"}, ""
    )
    assert result.state == MANUAL


# -- degree -------------------------------------------------------------------

def test_degree_master_matches_page_wording() -> None:
    result = check_degree(
        profile(degree_level="master"),
        {"degree_levels": "one-year master's degrees"},
        "",
    )
    assert result.state == SATISFIED


def test_degree_conflict_is_not_satisfied() -> None:
    result = check_degree(
        profile(degree_level="bachelor"), {"degree_levels": "PhD only"}, ""
    )
    assert result.state == NOT_SATISFIED


def test_degree_free_text_profile_and_page_are_manual() -> None:
    page = check_degree(profile(), {"degree_levels": "level 7 qualification"}, "")
    assert page.state == MANUAL
    student = check_degree(
        profile(degree_level="diploma in nursing"), {"degree_levels": "master"}, ""
    )
    assert student.state == MANUAL


# -- language -----------------------------------------------------------------

def test_language_ielts_meets_threshold() -> None:
    result = check_language(
        profile(ielts="7.0"), {"language_requirement": "IELTS: 6.5 overall"}, ""
    )
    assert result.state == SATISFIED


def test_language_ielts_below_threshold() -> None:
    result = check_language(
        profile(ielts="5.5"), {"language_requirement": "IELTS 6.5 minimum"}, ""
    )
    assert result.state == NOT_SATISFIED


def test_language_no_score_is_unknown() -> None:
    result = check_language(
        profile(ielts=""), {"language_requirement": "IELTS 6.5"}, ""
    )
    assert result.state == UNKNOWN


def test_language_alternative_pathway_can_satisfy() -> None:
    result = check_language(
        profile(ielts="5.5", toefl="100"),
        {"language_requirement": "IELTS 6.5 or TOEFL 90"},
        "",
    )
    assert result.state == SATISFIED


def test_language_one_low_other_missing_is_manual() -> None:
    result = check_language(
        profile(ielts="5.5", toefl=""),
        {"language_requirement": "IELTS 6.5 or TOEFL 90"},
        "",
    )
    assert result.state == MANUAL


def test_language_unreadable_wording_is_manual() -> None:
    result = check_language(
        profile(), {"language_requirement": "Good command of English"}, ""
    )
    assert result.state == MANUAL


# -- academic -----------------------------------------------------------------

def test_academic_same_scale_compares() -> None:
    result = check_academic(
        profile(gpa="3.62", gpa_scale="4.0"),
        {"academic_requirement": "Minimum GPA 3.50 / 4.00"},
        "",
    )
    assert result.state == SATISFIED


def test_academic_below_is_not_satisfied() -> None:
    result = check_academic(
        profile(gpa="3.00", gpa_scale="4.0"),
        {"academic_requirement": "Minimum GPA 3.50 / 4.00"},
        "",
    )
    assert result.state == NOT_SATISFIED


def test_academic_scale_mismatch_is_manual_not_converted() -> None:
    result = check_academic(
        profile(gpa="8.1", gpa_scale="10"),
        {"academic_requirement": "Minimum GPA 3.50 / 4.00"},
        "",
    )
    assert result.state == MANUAL
    assert "convert" in result.explanation


def test_academic_non_gpa_requirement_is_manual() -> None:
    result = check_academic(
        profile(), {"academic_requirement": "First class honours degree"}, ""
    )
    assert result.state == MANUAL


# -- deadline -----------------------------------------------------------------

def test_deadline_future_is_satisfied() -> None:
    result = check_deadline(profile(), {"deadline": "1 February 2027"}, "", today=TODAY)
    assert result.state == SATISFIED


def test_deadline_past_is_not_satisfied() -> None:
    result = check_deadline(profile(), {"deadline": "1 February 2026"}, "", today=TODAY)
    assert result.state == NOT_SATISFIED


def test_deadline_ambiguous_wording_is_manual() -> None:
    result = check_deadline(
        profile(), {"deadline": "Applications open in November"}, "", today=TODAY
    )
    assert result.state == MANUAL


def test_deadline_numeric_dates_are_not_guessed() -> None:
    result = check_deadline(profile(), {"deadline": "01/02/2026"}, "", today=TODAY)
    assert result.state == MANUAL


# -- verdicts and ranking ------------------------------------------------------

def test_verdict_never_claims_eligibility() -> None:
    reports = [
        evaluate(profile(), row(deadline="1 February 2027"), today=TODAY),
        evaluate(profile(), row(), today=TODAY),
        evaluate(
            profile(),
            row(eligible_nationalities="India", deadline="1 February 2027"),
            today=TODAY,
        ),
    ]
    for report in reports:
        assert "eligible" not in report.verdict().casefold()
        assert "%" not in report.verdict()


def test_verdict_reports_conflicts() -> None:
    report = evaluate(
        profile(),
        row(eligible_nationalities="India", deadline="1 February 2027"),
        today=TODAY,
    )
    assert report.verdict().startswith("Conflicts")


def test_verdict_reports_open_checks_not_success() -> None:
    report = evaluate(profile(ielts=""), row(), today=TODAY)
    assert report.verdict().startswith("Potential only")


def test_all_satisfied_verdict_still_asks_for_confirmation() -> None:
    report = evaluate(
        profile(),
        row(
            eligible_nationalities="Nepal",
            degree_levels="bachelor degrees",
            language_requirement="IELTS 6.5",
            academic_requirement="GPA 3.50 / 4.00",
            deadline="1 February 2027",
        ),
        today=TODAY,
    )
    assert report.conflicts() == ()
    assert report.open_checks() == ()
    verdict = report.verdict()
    assert verdict.startswith("No conflicts found")
    assert "confirm on the official page" in verdict


def test_ranking_is_deterministic_and_conflicts_sort_last() -> None:
    clean = evaluate(
        profile(),
        row(
            title="Clean",
            eligible_nationalities="Nepal",
            degree_levels="bachelor",
            language_requirement="IELTS 6.5",
            academic_requirement="GPA 3.50 / 4.00",
            deadline="1 February 2027",
        ),
        today=TODAY,
    )
    partial = evaluate(profile(), row(title="Partial"), today=TODAY)
    conflict = evaluate(
        profile(),
        row(title="Conflict", eligible_nationalities="India"),
        today=TODAY,
    )
    ordered = sorted([conflict, partial, clean], key=EligibilityReport.rank_key)
    assert [report.title for report in ordered] == ["Clean", "Partial", "Conflict"]

    rows = [
        dict(row(title="Conflict", eligible_nationalities="India")),
        dict(row(title="Partial")),
        dict(
            row(
                title="Clean",
                eligible_nationalities="Nepal",
                degree_levels="bachelor",
                language_requirement="IELTS 6.5",
                academic_requirement="GPA 3.50 / 4.00",
                deadline="1 February 2027",
            )
        ),
    ]
    first = [r.title for r in evaluate_all(profile(), rows, today=TODAY)]
    second = [r.title for r in evaluate_all(profile(), list(rows), today=TODAY)]
    assert first == second == ["Clean", "Partial", "Conflict"]


def test_evaluate_tolerates_missing_record_data() -> None:
    report = evaluate(profile(), {"id": 9, "title": "Empty"}, today=TODAY)
    assert all(r.state == UNKNOWN for r in report.requirements)
    assert report.verdict().startswith("Potential only")

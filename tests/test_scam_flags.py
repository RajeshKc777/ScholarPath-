"""Warning signs on a record (G158).

A sign is a fact about a page: it talks about money, it is not on an official
domain, it has no source, or it states no deadline. The tests check that every
sign fires when it should, that a lookalike domain is caught, and that the
wording never turns into a verdict.
"""

from __future__ import annotations

import copy

from scholarpath.scam_flags import (
    KIND_DOMAIN,
    KIND_MISSING_DEADLINE,
    KIND_MISSING_SOURCE,
    KIND_PAYMENT,
    KIND_PAYMENT_NOT_CHECKED,
    evaluate_signs,
    signs_summary,
)


def record(**overrides) -> dict:
    base = {
        "id": 1,
        "title": "OPEN GRANT 2026",
        "final_url": "https://scholarships.university.edu/open-grant",
        "requested_url": "https://scholarships.university.edu/open-grant",
        "deadline_text": "5 November 2026",
        "deadline_date": "2026-11-05",
        "page_text": "Deadline: 5 November 2026. Apply free of charge.",
        "data": {"values": {"deadline": "5 November 2026"}},
    }
    base.update(overrides)
    return base


def kinds(signs) -> list[str]:
    return [sign.kind for sign in signs]


def test_an_official_page_has_no_warning_signs() -> None:
    signs = evaluate_signs(record())
    assert kinds(signs) == []


def test_payment_wording_on_the_page_is_flagged() -> None:
    signs = evaluate_signs(
        record(
            page_text=(
                "OPEN GRANT 2026\nDeadline: 5 November 2026\n"
                "A non-refundable application fee of USD 50 is required."
            )
        )
    )
    payment = [sign for sign in signs if sign.kind == KIND_PAYMENT]
    assert len(payment) == 1
    assert "application fee" in payment[0].detail
    assert "non-refundable application fee" in payment[0].evidence.casefold()


def test_the_evidence_is_the_sentence_of_the_page() -> None:
    signs = evaluate_signs(
        record(
            page_text=(
                "OPEN GRANT 2026\n"
                "Deadline: 5 November 2026\n"
                "Please pay a fee of EUR 20 before you apply.\n"
            )
        )
    )
    payment = [sign for sign in signs if sign.kind == KIND_PAYMENT][0]
    assert "pay a fee" in payment.evidence


def test_a_page_that_mentions_no_payment_is_not_flagged_for_it() -> None:
    signs = evaluate_signs(record(page_text="Deadline: 5 November 2026. Fully funded."))
    assert KIND_PAYMENT not in kinds(signs)


def test_a_page_without_stored_text_says_the_check_was_not_possible() -> None:
    signs = evaluate_signs(record(page_text=""))
    assert KIND_PAYMENT_NOT_CHECKED in kinds(signs)
    note = [sign for sign in signs if sign.kind == KIND_PAYMENT_NOT_CHECKED][0]
    assert "could not" in note.detail.casefold()
    assert "re-check" in note.detail.casefold()


def test_a_lookalike_domain_is_flagged_and_named() -> None:
    signs = evaluate_signs(
        record(final_url="https://harvard.edu.fake.com/scholarship", page_text="")
    )
    domain = [sign for sign in signs if sign.kind == KIND_DOMAIN][0]
    assert "harvard.edu" in domain.detail
    assert "fake.com" in domain.detail


def test_a_lookalike_of_a_scholarship_body_is_flagged() -> None:
    signs = evaluate_signs(
        record(final_url="https://chevening-scholarships.org/apply", page_text="")
    )
    assert KIND_DOMAIN in kinds(signs)


def test_a_domain_the_student_trusts_is_not_flagged() -> None:
    signs = evaluate_signs(
        record(final_url="https://www.chevening.org/scholarships/", page_text=""),
        trusted_domains=["chevening.org"],
    )
    assert KIND_DOMAIN not in kinds(signs)


def test_the_trusted_list_is_matched_exactly_not_as_a_substring() -> None:
    signs = evaluate_signs(
        record(final_url="https://chevening.org.example.com/x", page_text=""),
        trusted_domains=["chevening.org"],
    )
    assert KIND_DOMAIN in kinds(signs)


def test_a_record_without_a_source_is_flagged() -> None:
    signs = evaluate_signs(record(final_url="", requested_url="", page_text=""))
    assert KIND_MISSING_SOURCE in kinds(signs)


def test_a_record_without_a_deadline_is_flagged() -> None:
    signs = evaluate_signs(
        record(
            deadline_text="",
            deadline_date=None,
            data={"values": {}},
            page_text="Apply now.",
        )
    )
    assert KIND_MISSING_DEADLINE in kinds(signs)


def test_the_wording_never_calls_a_page_a_fraud_or_a_trusted_one() -> None:
    signs = evaluate_signs(
        record(
            final_url="https://harvard.edu.fake.com/x",
            page_text="Pay a fee of USD 500 to release the scholarship.",
            deadline_text="",
            deadline_date=None,
        )
    )
    words = " ".join(
        f"{sign.headline} {sign.detail} {sign.evidence}" for sign in signs
    ).casefold()
    assert "scam" not in words
    assert "safe" not in words
    assert "fraud" not in words
    assert "warning sign" in signs_summary(signs).casefold()


def test_the_record_is_never_changed_by_the_check() -> None:
    original = record()
    before = copy.deepcopy(original)
    evaluate_signs(original)
    assert original == before


def test_the_summary_counts_the_warnings() -> None:
    signs = evaluate_signs(
        record(final_url="https://chevening-scholarships.org/x", page_text="")
    )
    assert "warning sign" in signs_summary(signs).casefold()

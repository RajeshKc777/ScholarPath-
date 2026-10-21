"""Warning signs on a record - things worth a second look, said plainly.

The app never tells a student that a page is genuine, and it never tells them
that a page is dishonest. It can only report **warning signs**: facts about
the page that a careful applicant would want to see before they type their
bank details into a form.

Four signs are looked for:

1. **Payment wording** - the page talks about a fee, a payment, a transfer or
   a deposit. The sentence that triggered it is quoted, so "no application fee"
   reads as clearly as "a processing fee of USD 50".
2. **A domain that is neither official nor trusted** - the registrable domain
   is compared exactly against the official rules (`.edu`, `.ac.<cc>`,
   `.gov`, `.gov.<cc>`) and the student's own `trusted_domains`. A lookalike
   such as ``harvard.edu.fake.com`` is not official, and the sign says so.
3. **A missing source** - the record has no page address, so nothing about it
   can be checked.
4. **A missing deadline** - the page states no deadline, so nothing here can
   say whether the opportunity is still open.

A sign never hides, changes or deletes a record. The wording says "warning
sign"; it never calls a page a fraud and never calls a page trustworthy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from scholarpath.official import host_of, is_known_domain, is_official_domain, registrable_domain

#: The sign kinds, in the order they are reported.
KIND_PAYMENT = "payment-wording"
KIND_PAYMENT_NOT_CHECKED = "payment-wording-not-checked"
KIND_DOMAIN = "domain-not-official"
KIND_MISSING_SOURCE = "missing-source"
KIND_MISSING_DEADLINE = "missing-deadline"

#: Phrases that mean "this page asks for money". Matched as whole words, in
#: the order they are listed, so the most specific wording is reported first.
PAYMENT_PHRASES: tuple[str, ...] = (
    "application fee",
    "registration fee",
    "processing fee",
    "administrative fee",
    "service fee",
    "non-refundable fee",
    "processing charge",
    "service charge",
    "pay a fee",
    "pay the fee",
    "pay to apply",
    "payment is required",
    "payment required",
    "payment of",
    "fee of",
    "fee is",
    "bank transfer",
    "wire transfer",
    "bank details",
    "bank account",
    "western union",
    "moneygram",
    "gift card",
    "bitcoin",
    "credit card",
    "deposit to apply",
)

_SEVERITY_WARNING = "warning sign"
_SEVERITY_NOTE = "note"

_MAX_EVIDENCE = 240


@dataclass(frozen=True)
class WarningSign:
    """One thing worth a second look, and why it is there."""

    kind: str
    headline: str
    detail: str
    evidence: str = ""
    severity: str = _SEVERITY_WARNING

    @property
    def is_warning(self) -> bool:
        return self.severity == _SEVERITY_WARNING


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part and part.strip()]


def _evidence_for(text: str, phrase: str) -> str:
    """The sentence of the page that holds the phrase, cut to a readable size."""
    lowered = text.casefold()
    index = lowered.find(phrase)
    if index < 0:
        return ""
    for sentence in _sentences(text):
        if phrase in sentence.casefold():
            return _clip(sentence)
    start = max(0, index - 120)
    return _clip(text[start : start + _MAX_EVIDENCE])


def _clip(text: str, limit: int = _MAX_EVIDENCE) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."


def _record_data(record: dict) -> dict:
    data = record.get("data")
    return data if isinstance(data, dict) else {}


def _deadline_text(record: dict) -> str:
    deadline = str(record.get("deadline_text") or "").strip()
    if deadline:
        return deadline
    values = _record_data(record).get("values")
    if isinstance(values, dict):
        return str(values.get("deadline") or "").strip()
    return ""


def _source_url(record: dict) -> str:
    return str(record.get("final_url") or record.get("requested_url") or "").strip()


def _page_text(record: dict, page_text: str) -> str:
    if page_text:
        return page_text
    return str(record.get("page_text") or "")


def official_looking_prefix(host: str) -> str:
    """An official-looking domain hidden inside another domain, if there is one.

    "harvard.edu.fake.com" hides "harvard.edu" - the name looks official while
    the site itself is "fake.com".
    """
    labels = (host or "").lower().strip(".").split(".")
    for count in range(len(labels) - 1, 0, -1):
        candidate = ".".join(labels[:count])
        if is_official_domain(candidate):
            return candidate
    return ""


def evaluate_signs(
    record: dict,
    *,
    page_text: str = "",
    trusted_domains: Iterable[str] = (),
) -> list[WarningSign]:
    """The warning signs for one record. Never raises, never changes it."""
    signs: list[WarningSign] = []
    url = _source_url(record)
    text = _page_text(record, page_text)

    # 1. payment wording
    if text.strip():
        lowered = text.casefold()
        for phrase in PAYMENT_PHRASES:
            if phrase in lowered:
                signs.append(
                    WarningSign(
                        kind=KIND_PAYMENT,
                        headline="The page talks about a payment",
                        detail=(
                            "The page uses the words "
                            f"\"{phrase}\". Read that part of the page before "
                            "you send anything anywhere."
                        ),
                        evidence=_evidence_for(text, phrase),
                    )
                )
                break
    else:
        signs.append(
            WarningSign(
                kind=KIND_PAYMENT_NOT_CHECKED,
                headline="Payment wording could not be checked",
                detail=(
                    "The text of the page was not kept, so payment wording "
                    "could not be looked for. Re-check the page to look."
                ),
                severity=_SEVERITY_NOTE,
            )
        )

    # 2. the domain
    if not url:
        signs.append(
            WarningSign(
                kind=KIND_MISSING_SOURCE,
                headline="No source page",
                detail=(
                    "This record has no page address, so nothing about it can "
                    "be checked against the official page."
                ),
            )
        )
    else:
        host = host_of(url)
        if not is_known_domain(host, trusted_domains):
            registrable = registrable_domain(host) or host
            lookalike = official_looking_prefix(host)
            if lookalike:
                detail = (
                    f"The name contains \"{lookalike}\", but this site's own "
                    f"domain is \"{registrable}\". A page can look official "
                    "and still not be the official site."
                )
            else:
                detail = (
                    f"The page is on \"{registrable}\", which is not an "
                    "official or government domain and is not in your trusted "
                    "list. Check the address on the official site before you "
                    "apply."
                )
            signs.append(
                WarningSign(
                    kind=KIND_DOMAIN,
                    headline="The domain is not an official one",
                    detail=detail,
                    evidence=url,
                )
            )

    # 3. the deadline
    if not _deadline_text(record):
        signs.append(
            WarningSign(
                kind=KIND_MISSING_DEADLINE,
                headline="The page states no deadline",
                detail=(
                    "The page names no closing date, so nothing here can say "
                    "whether the opportunity is still open. Open the page and "
                    "look for the date."
                ),
                severity=_SEVERITY_NOTE,
            )
        )

    return signs


def signs_summary(signs: list[WarningSign]) -> str:
    """One line for a card: how many warning signs were found."""
    warnings = [sign for sign in signs if sign.is_warning]
    if not warnings:
        if signs:
            return "No warning signs; 1 note to read"
        return "No warning signs found"
    return f"{len(warnings)} warning sign(s) to read"


def warning_text(signs: list[WarningSign]) -> str:
    """The sign headlines, one per line, for a tooltip or a plain panel."""
    return "\n".join(f"- {sign.headline}: {sign.detail}" for sign in signs)

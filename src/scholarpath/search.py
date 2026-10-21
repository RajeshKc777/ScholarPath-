"""Search and filters over the local catalog (Phase 2, G149).

This is a **reading aid, not a ranking of students**: it matches the words and
fields that a page actually states, and it reports dates honestly ("open",
"closed", "no readable date"). It never decides that anyone is eligible - that
is a separate, deterministic step (`eligibility.evaluate`) with its own honest
unknowns.

Nothing here touches the network: the catalog is already on this machine.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

# -- levels -------------------------------------------------------------------

LEVEL_ANY = "any"
LEVEL_BACHELOR = "bachelor"
LEVEL_MASTER = "master"
LEVEL_PHD = "phd"

LEVEL_CHOICES: tuple[tuple[str, str], ...] = (
    (LEVEL_ANY, "Any level"),
    (LEVEL_BACHELOR, "Bachelor's"),
    (LEVEL_MASTER, "Master's"),
    (LEVEL_PHD, "PhD / doctorate"),
)

#: Words that may describe each level on a page. Matched as whole words, so
#: "BA" matches but "bachelor" is not hidden inside "bachelorette".
_LEVEL_WORDS: dict[str, frozenset[str]] = {
    LEVEL_BACHELOR: frozenset(
        {
            "bachelor", "bachelors", "undergraduate", "bsc", "beng", "bcom",
            "ba", "btec",
        }
    ),
    LEVEL_MASTER: frozenset(
        {
            "master", "masters", "postgraduate", "msc", "meng", "mba", "mres",
            "mphil", "ma",
        }
    ),
    LEVEL_PHD: frozenset(
        {"phd", "doctorate", "doctoral", "doctor", "dphil"}
    ),
}

# -- deadlines ----------------------------------------------------------------

DEADLINE_ANY = "any"
DEADLINE_OPEN = "open"
DEADLINE_SOON = "soon"
DEADLINE_CLOSED = "closed"
DEADLINE_UNKNOWN = "unknown"

DEADLINE_CHOICES: tuple[tuple[str, str], ...] = (
    (DEADLINE_ANY, "Any deadline"),
    (DEADLINE_OPEN, "Still open"),
    (DEADLINE_SOON, "Closing within 90 days"),
    (DEADLINE_CLOSED, "Already closed"),
    (DEADLINE_UNKNOWN, "No readable date"),
)

#: How many days ahead "closing soon" looks.
SOON_DAYS = 90


# -- text ---------------------------------------------------------------------

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-")
_QUOTES = dict.fromkeys(map(ord, "\u2018\u2019\u201a\u201b\u2032"), "'")
_QUOTES.update(dict.fromkeys(map(ord, "\u201c\u201d\u201e\u201f\u2033"), '"'))


def normalise_text(value: str) -> str:
    """Fold a value for matching: accents, case, quote/dash style, spacing."""
    text = unicodedata.normalize("NFKD", value or "")
    # Drop combining marks so "Türkiye" is found by someone typing "turkiye".
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.translate(_DASHES).translate(_QUOTES)
    return " ".join(text.casefold().split())


def words_in(value: str) -> list[str]:
    """The whole words of a value, punctuation removed."""
    cleaned = normalise_text(value)
    for separator in ("'", '"', ",", ".", ":", ";", "/", "(", ")", "[", "]", "-", "|"):
        cleaned = cleaned.replace(separator, " ")
    return [word for word in cleaned.split() if word]


def _haystack(record: dict) -> str:
    """Everything about a record that a text search may look at."""
    parts = [
        record.get("title", ""),
        record.get("provider", ""),
        record.get("provider_domain", ""),
        record.get("institution", ""),
        record.get("countries", ""),
        record.get("level", ""),
        record.get("fields_of_study", ""),
        record.get("funding_type", ""),
        record.get("amount_text", ""),
        record.get("deadline_text", ""),
        record.get("language_req", ""),
    ]
    return normalise_text(" \n ".join(str(part or "") for part in parts))


def text_matches(record: dict, query: str) -> bool:
    """True when every word of the query appears somewhere on the record."""
    words = words_in(query)
    if not words:
        return True
    haystack = _haystack(record)
    return all(word in haystack for word in words)


def level_matches(record: dict, level: str) -> bool:
    """True when the page's own level wording names that level."""
    if level == LEVEL_ANY or not level:
        return True
    wanted = _LEVEL_WORDS.get(level, frozenset())
    if not wanted:
        return True
    return bool(wanted.intersection(words_in(record.get("level", ""))))


# -- deadlines ----------------------------------------------------------------


def parsed_deadline(record: dict) -> date | None:
    """The stored, unambiguous deadline date (never guessed from text)."""
    raw = str(record.get("deadline_date") or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def deadline_state(record: dict, today: date | None = None) -> str:
    """`open`, `soon`, `closed` or `unknown` - from the stored date only."""
    current = today or date.today()
    deadline = parsed_deadline(record)
    if deadline is None:
        return DEADLINE_UNKNOWN
    if deadline < current:
        return DEADLINE_CLOSED
    if deadline <= current + timedelta(days=SOON_DAYS):
        return DEADLINE_SOON
    return DEADLINE_OPEN


def deadline_phrase(record: dict, today: date | None = None) -> str:
    """Plain words for the card. The page's own wording stays on the record."""
    current = today or date.today()
    state = deadline_state(record, today)
    deadline = parsed_deadline(record)
    if state == DEADLINE_UNKNOWN:
        return "No readable deadline date on the page"
    assert deadline is not None
    days = (deadline - current).days
    if state == DEADLINE_CLOSED:
        return f"Closed on {deadline.isoformat()}"
    if days == 0:
        return f"Closes today ({deadline.isoformat()})"
    if days == 1:
        return "Closes tomorrow"
    if state == DEADLINE_SOON:
        return f"Closes in {days} days ({deadline.isoformat()})"
    return f"Open until {deadline.isoformat()} ({days} days)"


def deadline_matches(record: dict, choice: str, today: date | None = None) -> bool:
    if choice in ("", DEADLINE_ANY):
        return True
    state = deadline_state(record, today)
    if choice == DEADLINE_OPEN:
        return state in (DEADLINE_OPEN, DEADLINE_SOON)
    if choice == DEADLINE_UNKNOWN:
        return state == DEADLINE_UNKNOWN
    return state == choice


# -- the search ---------------------------------------------------------------


@dataclass(frozen=True)
class SearchFilters:
    """What the student typed. Empty values mean "do not filter"."""

    text: str = ""
    level: str = LEVEL_ANY
    country: str = ""
    field: str = ""
    provider: str = ""
    deadline: str = DEADLINE_ANY

    def any_set(self) -> bool:
        return bool(
            words_in(self.text)
            or self.level not in ("", LEVEL_ANY)
            or words_in(self.country)
            or words_in(self.field)
            or words_in(self.provider)
            or self.deadline not in ("", DEADLINE_ANY)
        )


@dataclass(frozen=True)
class SearchHit:
    """One matching record, with the date state worked out once."""

    record: dict
    deadline_state: str
    deadline_phrase: str
    deadline_date: date | None

    @property
    def title(self) -> str:
        return str(self.record.get("title") or self.record.get("page_title") or "")


def matches(record: dict, filters: SearchFilters, today: date | None = None) -> bool:
    if not text_matches(record, filters.text):
        return False
    if not level_matches(record, filters.level):
        return False
    if filters.country and not text_matches(
        {"countries": record.get("countries", "")}, filters.country
    ):
        return False
    if filters.field and not text_matches(
        {"fields_of_study": record.get("fields_of_study", "")}, filters.field
    ):
        return False
    if filters.provider and not text_matches(
        {"provider": record.get("provider", "")}, filters.provider
    ):
        return False
    return deadline_matches(record, filters.deadline, today)


def _order_key(hit: SearchHit) -> tuple:
    """Open first (closest deadline first), then no date, then closed."""
    if hit.deadline_state in (DEADLINE_OPEN, DEADLINE_SOON):
        return (0, hit.deadline_date or date.max, hit.title.casefold())
    if hit.deadline_state == DEADLINE_UNKNOWN:
        return (1, date.max, hit.title.casefold())
    return (2, -(hit.deadline_date or date.min).toordinal(), hit.title.casefold())


def search_records(
    records: list[dict] | tuple[dict, ...],
    filters: SearchFilters,
    today: date | None = None,
) -> list[SearchHit]:
    """Every matching record, in a fixed, explainable order."""
    current = today or date.today()
    hits = [
        SearchHit(
            record=record,
            deadline_state=deadline_state(record, current),
            deadline_phrase=deadline_phrase(record, current),
            deadline_date=parsed_deadline(record),
        )
        for record in records
        if matches(record, filters, current)
    ]
    return sorted(hits, key=_order_key)


def summary_line(total: int, hits: list[SearchHit]) -> str:
    """The honest count under the filters."""
    if total == 0:
        return "The catalog is empty."
    open_now = sum(
        1 for hit in hits if hit.deadline_state in (DEADLINE_OPEN, DEADLINE_SOON)
    )
    if not hits:
        return f"No record matches these filters ({total} in the catalog)."
    return (
        f"{len(hits)} of {total} record(s) match \u2014 {open_now} with an open "
        "deadline."
    )

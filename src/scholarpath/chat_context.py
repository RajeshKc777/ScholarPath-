"""What the chat may know before it answers (G181-G183).

The chat must not ask the student for facts the app already holds. The saved
profile is turned into a **compact summary** that names only the fields the
owner listed: degree level, GPA and its scale, nationality, preferred
countries, funding need and language scores. The student's name and the
documents are **never** part of it - only the fields below are read.

The summary travels with the chat message to the model service, so Settings
discloses it and a switch (`privacy.chat_profile`) turns it off. With the
switch off the chat is given nothing.

The second thing the chat may use is the **verified catalog**: the records
this device already holds, each read from its official page and checked word
for word. They go to the model before any web result, with their source
address and the date they were last verified, so the student is told what is
checked and what is only a lead.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from scholarpath.official import is_official_domain
from scholarpath.search import (
    LEVEL_BACHELOR,
    LEVEL_MASTER,
    LEVEL_PHD,
    SearchFilters,
    SearchHit,
    level_matches,
    search_records,
)

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


# -- the links a reply names (G184) ----------------------------------------------

_URL_IN_TEXT_RE = re.compile(r"https?://[^\s<>\"']+")


def official_links(text: str) -> list[str]:
    """The official-looking addresses a reply names, in the order they appear.

    A third-party address is left out: the app may not fetch it as if it were
    an official page.
    """
    links: list[str] = []
    for raw in _URL_IN_TEXT_RE.findall(text or ""):
        url = raw.rstrip(".,;:!?)]}'\"")
        if not url:
            continue
        host = urlsplit(url).netloc
        if not host or not is_official_domain(host):
            continue
        if url not in links:
            links.append(url)
    return links


# -- levels (G183) ---------------------------------------------------------------

#: The level words, in the order they are checked.
_RECORD_LEVELS = (LEVEL_BACHELOR, LEVEL_MASTER, LEVEL_PHD)

#: The study levels that are already behind a student, per profile value. A
#: "bachelor" in the profile means the degree is **completed**, so a
#: scholarship for bachelor's study is not for that student.
_BEHIND = {
    "bachelor": (LEVEL_BACHELOR,),
    "master": (LEVEL_BACHELOR,),
    "phd": (LEVEL_BACHELOR, LEVEL_MASTER),
    "postdoc": (LEVEL_BACHELOR, LEVEL_MASTER, LEVEL_PHD),
}

_LEVEL_NAMES = {
    LEVEL_BACHELOR: "bachelor's study",
    LEVEL_MASTER: "master's study",
    LEVEL_PHD: "doctoral study",
}


def level_note(profile: dict | None) -> str:
    """The one-line level rule for this student ("" when the level is unknown)."""
    level = _text(profile.get("degree_level")) if profile else ""
    if level == "bachelor":
        return (
            "Level rule: the student's profile says a bachelor's degree is "
            "completed, so prefer graduate-level programmes (master's, PhD) "
            "and say in one line why you prefer them. If a programme or a "
            "record is for another level, say so plainly."
        )
    if level == "master":
        return (
            "Level rule: the student's profile says a master's degree is "
            "completed, so prefer doctoral and research programmes, and say "
            "in one line why you prefer them. If a programme or a record is "
            "for another level, say so plainly."
        )
    if level in ("phd", "postdoc"):
        return (
            "Level rule: the student's profile says they are already at "
            "doctoral or postdoctoral level, so prefer postdoctoral and "
            "research funding, and say in one line why. If a programme or a "
            "record is for another level, say so plainly."
        )
    return ""


def record_levels(record: dict) -> set[str]:
    """The levels the record's own page states."""
    return {
        level for level in _RECORD_LEVELS if level_matches(record, level)
    }


def level_flag(record: dict, profile: dict | None) -> str:
    """A note when the record is for a level the student is already past ("")."""
    level = _text(profile.get("degree_level")) if profile else ""
    behind = _BEHIND.get(level)
    if not behind:
        return ""
    for stated in record_levels(record):
        if stated in behind:
            return f"this one is for {_LEVEL_NAMES[stated]}, not for this student"
    return ""


# -- the verified catalog (G182) -------------------------------------------------

#: Words that say nothing about which record is meant: function words, and
#: the words every scholarship page uses.
STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "if", "then", "than", "so",
        "for", "from", "to", "of", "in", "on", "at", "by", "with", "without",
        "about", "as", "into", "over", "after", "before", "during", "is",
        "are", "was", "were", "be", "been", "am", "do", "does", "did", "can",
        "could", "will", "would", "shall", "should", "may", "might", "must",
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
        "they", "them", "their", "this", "that", "these", "those", "there",
        "here", "what", "which", "who", "whom", "whose", "when", "where",
        "why", "how", "get", "got", "give", "tell", "show", "find", "found",
        "know", "like", "please", "help", "want", "need", "any", "some",
        "scholarship", "scholarships", "funding", "funded", "opportunity",
        "opportunities", "programme", "programmes", "program", "programs",
        "study", "studies", "apply", "application", "applications", "award",
        "awards", "grant", "grants", "university", "universities", "college",
    }
)


def content_words(message: str) -> list[str]:
    """The words of a message that can pick out a record."""
    words: list[str] = []
    for word in re.findall(r"[\w']+", (message or "").casefold()):
        if word in STOPWORDS or word in words:
            continue
        words.append(word)
    return words


def catalog_hits(
    records: list[dict] | tuple[dict, ...],
    message: str,
    limit: int = 3,
) -> list[SearchHit]:
    """The stored records that match a message, using Discover's own search.

    The same `search_records` the Discover page runs is used here, one
    content word at a time, so a whole sentence still finds the record that
    mentions it. Records that match more words come first.
    """
    words = content_words(message)
    if not words:
        return []
    scores: dict[str, tuple[int, SearchHit]] = {}
    for word in words:
        for hit in search_records(records, SearchFilters(text=word)):
            key = str(
                hit.record.get("id")
                or hit.record.get("canonical_key")
                or id(hit.record)
            )
            count, best = scores.get(key, (0, hit))
            scores[key] = (count + 1, best)
    ordered = sorted(
        scores.values(), key=lambda pair: (-pair[0], pair[1].title.casefold())
    )
    return [hit for _count, hit in ordered[:limit]]


def last_verified(record: dict) -> str:
    """The date the record was last checked against its page (or "")."""
    data = record.get("data")
    stamp = ""
    if isinstance(data, dict):
        stamp = str(data.get("last_checked_at") or "").strip()
    stamp = stamp or str(record.get("retrieved_at") or "").strip()
    return stamp[:10]


def source_of(record: dict) -> str:
    """The address the record was verified from."""
    for key in ("final_url", "requested_url", "apply_url"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return ""


def catalog_message(hits: list[SearchHit], profile: dict | None = None, limit: int = 3) -> str:
    """The verified records, ready for the model, with their provenance."""
    if not hits:
        return ""
    lines = [
        "Records already verified in your catalog (every value was read from "
        "the official page and checked word for word):",
    ]
    for index, hit in enumerate(hits[:limit], start=1):
        record = hit.record
        title = hit.title or "untitled record"
        provider = str(
            record.get("provider") or record.get("provider_domain") or ""
        ).strip()
        level = str(record.get("level") or "").strip() or "level not stated"
        source = source_of(record)
        verified = last_verified(record)
        parts = [title]
        if provider:
            parts.append(f"provider: {provider}")
        parts.append(f"level: {level}")
        parts.append(f"deadline: {hit.deadline_phrase}")
        if source:
            parts.append(f"source: {source}")
        if verified:
            parts.append(f"last verified: {verified}")
        flag = level_flag(record, profile)
        if flag:
            parts.append(flag)
        lines.append(f"{index}. " + " | ".join(parts))
    lines += [
        "",
        "Use these first, and say that they come from the verified catalog. "
        "When you name one, give its source address and the date it was last "
        "verified. Anything that comes from a web search is only an "
        "unverified lead: say so, and never call it verified.",
    ]
    return "\n".join(lines)

"""Human-sounding reply text (G131).

Models often answer in markdown: bold asterisks, dash bullets, heading
hashes, tables, horizontal rules. In a chat bubble that reads like a
generated document, and spoken aloud the symbols turn into noise. These
helpers keep every word the model wrote and remove the formatting, so the
bubble and the spoken reply both sound like a person talking.

`humanize_reply` is for the chat bubble (line breaks and links are kept);
`speech_text` is for the voice (one flowing stream, links replaced).
"""

from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://\S+")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]*)\)")
_FENCE_RE = re.compile(r"^[ \t]*```[^\n]*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]*", re.MULTILINE)
_RULE_RE = re.compile(r"^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^[ \t]*[-*+][ \t]+", re.MULTILINE)
_TABLE_RULE_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)+\|?[ \t]*$",
    re.MULTILINE,
)
_TABLE_ROW_RE = re.compile(r"^[ \t]*\|(.+)\|[ \t]*$", re.MULTILINE)
_STRONG_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.DOTALL)
_EM_RE = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_CODE_RE = re.compile(r"`([^`\n]*)`")
_STRAY_MARKS_RE = re.compile(r"\*{1,3}")
_DASH_RE = re.compile(r"[ \t]*-{2,}[ \t]*")
_SPACES_RE = re.compile(r"[ \t]{2,}")
_BLANKS_RE = re.compile(r"\n{3,}")


def _display_link(match: re.Match[str]) -> str:
    label = (match.group(1) or "").strip()
    target = (match.group(2) or "").strip()
    if label and target and label != target:
        return f"{label} ({target})"
    return label or target


def _speech_link(match: re.Match[str]) -> str:
    return (match.group(1) or match.group(2) or "").strip()


def _table_row(match: re.Match[str]) -> str:
    cells = [cell.strip() for cell in match.group(1).split("|")]
    return " \u00b7 ".join(cell for cell in cells if cell)


def humanize_reply(text: str) -> str:
    """Chat version of a model reply: the words kept, the markdown gone."""
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _FENCE_RE.sub("", cleaned)
    cleaned = _TABLE_RULE_RE.sub("", cleaned)
    cleaned = _TABLE_ROW_RE.sub(_table_row, cleaned)
    cleaned = _LINK_RE.sub(_display_link, cleaned)
    cleaned = _HEADING_RE.sub("", cleaned)
    cleaned = _RULE_RE.sub("", cleaned)
    cleaned = _BULLET_RE.sub("\u2022 ", cleaned)
    cleaned = _STRONG_RE.sub(lambda match: match.group(1) or match.group(2) or "", cleaned)
    cleaned = _EM_RE.sub(r"\1", cleaned)
    cleaned = _CODE_RE.sub(r"\1", cleaned)
    cleaned = _STRAY_MARKS_RE.sub("", cleaned)
    cleaned = _DASH_RE.sub(" \u2014 ", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))
    cleaned = _SPACES_RE.sub(" ", cleaned)
    cleaned = _BLANKS_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def speech_text(text: str) -> str:
    """Spoken version of a reply: one flowing line, links spoken as words."""
    if not text:
        return ""
    spoken = _LINK_RE.sub(_speech_link, text.replace("\r\n", "\n"))
    spoken = humanize_reply(spoken)
    spoken = _URL_RE.sub("link in the chat", spoken)
    spoken = spoken.replace("\u2022", " ")
    spoken = re.sub(r"\s+", " ", spoken)
    return spoken.strip()

"""Replies that read like a person wrote them (G131).

Markdown symbols must never reach the chat bubble or the voice: the student
should see and hear plain, warm prose even when the model answers in markdown.
"""

from __future__ import annotations

from scholarpath.gateway.base import ChatRequest, Message
from scholarpath.gateway.opencode import OpenCodeGateway
from scholarpath.identity import SYSTEM_PROMPT
from scholarpath.prose import humanize_reply, linkify_html, speech_text


def test_bold_and_italic_markers_disappear() -> None:
    assert humanize_reply("**Yes**, that *is* right.") == "Yes, that is right."


def test_double_dashes_become_a_real_dash() -> None:
    cleaned = humanize_reply("Deadline -- check the official page.")
    assert "--" not in cleaned
    assert "\u2014" in cleaned


def test_headings_and_horizontal_rules_are_removed() -> None:
    cleaned = humanize_reply("# Funding\n\n---\n\nIt covers one year.")
    assert "#" not in cleaned
    assert "---" not in cleaned
    assert "Funding" in cleaned
    assert "It covers one year." in cleaned


def test_dash_bullets_become_readable_dots() -> None:
    cleaned = humanize_reply("- IELTS score\n- Transcript")
    assert "- IELTS" not in cleaned
    assert "\u2022 IELTS score" in cleaned
    assert "\u2022 Transcript" in cleaned


def test_tables_become_plain_lines() -> None:
    cleaned = humanize_reply("| Item | Value |\n| --- | --- |\n| Deadline | Check the page |")
    assert "|" not in cleaned
    assert "Item \u00b7 Value" in cleaned
    assert "Deadline \u00b7 Check the page" in cleaned


def test_links_keep_their_label_and_target_in_the_bubble() -> None:
    cleaned = humanize_reply("See [the page](https://example.org/x).")
    assert "the page" in cleaned
    assert "https://example.org/x" in cleaned


def test_speech_reads_clean_and_replaces_links() -> None:
    spoken = speech_text("**Chevening** -- see [the page](https://example.org/x).")
    assert "**" not in spoken
    assert "--" not in spoken
    assert "\n" not in spoken
    assert "Chevening \u2014 see the page." == spoken
    bare = speech_text("Read https://example.org/x for details")
    assert "https://" not in bare
    assert "link in the chat" in bare


def test_empty_text_stays_empty() -> None:
    assert humanize_reply("") == ""
    assert speech_text("") == ""
    assert linkify_html("") == ""


# -- G177: every web address in a reply is a clickable link ----------------------


def test_a_web_address_becomes_a_clickable_link() -> None:
    html = linkify_html("Check https://example.org/x for the deadline.")
    assert '<a href="https://example.org/x">https://example.org/x</a>' in html


def test_the_punctuation_after_an_address_stays_outside_the_link() -> None:
    html = linkify_html("See https://example.org/x.")
    assert '<a href="https://example.org/x">https://example.org/x</a>.' in html


def test_the_words_are_escaped_and_the_line_breaks_survive() -> None:
    html = linkify_html("a < b & c\n\nnext line")
    assert "a &lt; b &amp; c" in html
    assert "<br>" in html


def test_ordinary_words_are_not_turned_into_links() -> None:
    assert "<a " not in linkify_html("No address in this sentence.")
    assert "<a " not in linkify_html("Write to info@example.org for it.")


def test_the_spoken_reply_still_says_link_in_the_chat() -> None:
    spoken = speech_text("See https://example.org/x for the details.")
    assert "https://" not in spoken
    assert "link in the chat" in spoken


def test_system_prompt_forbids_markdown() -> None:
    lowered = SYSTEM_PROMPT.casefold()
    assert "markdown" in lowered
    assert "no asterisks" in lowered
    assert "contractions" in lowered


def test_live_prompt_keeps_app_rules_as_instructions() -> None:
    prompt = OpenCodeGateway._compose_prompt(
        ChatRequest(
            messages=[
                Message(role="system", content="RULE-XYZ stays private"),
                Message(role="user", content="hello"),
            ]
        )
    )
    assert "RULE-XYZ stays private" in prompt
    assert "Assistant: RULE-XYZ" not in prompt
    assert "User: hello" in prompt

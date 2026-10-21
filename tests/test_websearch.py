"""Web search for the chat: parsing, guards and the turn flow (G136)."""

from __future__ import annotations

import json

from scholarpath.ui.chat_controller import ChatController, parse_search_request
from scholarpath.websearch import (
    MAX_QUERY,
    SearchError,
    SearchResult,
    clean_query,
    format_results,
    parse_results,
)

RESULT_HTML = """
<table>
  <tr><td><a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.chevening.org%2Fscholarships%2F&amp;rut=abc" class='result-link'>Chevening Scholarships</a></td></tr>
  <tr><td class='result-snippet'>Fully-funded one-year master's degrees in the UK.</td></tr>
  <tr><td><a rel="nofollow" href="/scholarships/need-based" class='result-link'>Need-based bursary</a></td></tr>
  <tr><td class='result-snippet'>For students from low-income backgrounds.</td></tr>
  <tr><td><a rel="nofollow" href="mailto:info@example.org" class='result-link'>Scholarship enquiries</a></td></tr>
</table>
"""


class FakeGateway:
    name = "fake-local"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.requests = []

    def complete(self, request):  # noqa: ANN001
        from scholarpath.gateway.base import ChatResponse

        self.requests.append(request)
        reply = self.replies[min(len(self.requests) - 1, len(self.replies) - 1)]
        return ChatResponse(text=reply, model="fake-model")


def test_a_search_request_is_recognised() -> None:
    assert parse_search_request('{"search": "chevening scholarship 2027"}') == (
        "chevening scholarship 2027"
    )


def test_a_fenced_search_request_is_recognised() -> None:
    assert parse_search_request('```json\n{"search": "uk masters"}\n```') == "uk masters"


def test_ordinary_replies_are_not_search_requests() -> None:
    assert parse_search_request("Here are some ideas for you.") is None
    assert parse_search_request("") is None
    assert parse_search_request('{"search": ""}') is None
    assert parse_search_request('{"search": 42}') is None
    assert parse_search_request("{not json}") is None


def test_the_query_is_capped_and_collapsed() -> None:
    assert clean_query("  uk   scholarship  ") == "uk scholarship"
    assert len(clean_query("x" * 500)) == MAX_QUERY


def test_results_are_parsed_and_redirects_unwrapped() -> None:
    results = parse_results(RESULT_HTML)
    assert [result.url for result in results] == [
        "https://www.chevening.org/scholarships/",
        "https://lite.duckduckgo.com/scholarships/need-based",
    ]
    assert results[0].title == "Chevening Scholarships"
    assert "Fully-funded" in results[0].snippet


def test_non_http_links_are_dropped() -> None:
    results = parse_results(
        "<a class='result-link' href='mailto:info@example.org'>Scholarship</a>"
    )
    assert results == []


def test_official_domains_are_listed_first_and_labelled() -> None:
    page = (
        "<a class='result-link' href='https://blog.example.com/scholarship'>Blog</a>"
        "<a class='result-link' href='https://www.chevening.org/scholarships'>Chevening</a>"
    )
    results = parse_results(page)
    assert [result.url for result in results] == [
        "https://www.chevening.org/scholarships",
        "https://blog.example.com/scholarship",
    ]
    assert results[0].official_looking
    assert not results[1].official_looking
    block = format_results("uk scholarship", results)
    assert "official-looking domain" in block
    assert "not an official domain" in block


def test_the_result_block_marks_the_content_as_untrusted() -> None:
    block = format_results(
        "uk scholarship",
        [SearchResult(title="Chevening", url="https://chevening.org/x", snippet="One year")],
    )
    assert "untrusted" in block.casefold()
    assert "https://chevening.org/x" in block
    assert "Never invent" in block


def test_a_search_turn_answers_from_the_results() -> None:
    gateway = FakeGateway(
        [
            '{"search": "chevening scholarship 2027"}',
            "Chevening funds one year of study in the UK (chevening.org).",
        ]
    )
    calls: list[str] = []
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: (
            calls.append(query)
            or [SearchResult(title="Chevening", url="https://chevening.org/x", snippet="One year")]
        ),
    )
    controller.send("search scholarship in uk")

    assert calls == ["chevening scholarship 2027"]
    assert len(gateway.requests) == 2, "the model is asked again with the results"
    follow_up = gateway.requests[1].messages[-1].content
    assert "https://chevening.org/x" in follow_up
    assert "untrusted" in follow_up.casefold()
    assert controller.history[-1].text.startswith("Chevening funds one year")
    assert controller.last_search == "chevening scholarship 2027"
    assert not controller.history[-1].error


def test_the_search_request_never_enters_the_history() -> None:
    gateway = FakeGateway(['{"search": "grant"}', "Here is what I found."])
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: [SearchResult(title="T", url="https://example.org/x")],
    )
    controller.send("find a grant")
    texts = [turn.text for turn in controller.history]
    assert '{"search"' not in " ".join(texts)


def test_a_failed_search_becomes_an_honest_error_turn() -> None:
    gateway = FakeGateway(['{"search": "grant"}', "never used"])

    def failing(query: str) -> list[SearchResult]:
        raise SearchError("The web search service could not be reached.")

    controller = ChatController(
        gateway, "fake-model", dispatch=lambda work: work(), searcher=failing
    )
    failures: list[str] = []
    controller.failed.connect(failures.append)
    controller.send("find a grant")

    assert failures and "could not be reached" in failures[0]
    assert controller.history[-1].error
    assert len(gateway.requests) == 1, "no second model call without results"


def test_search_can_be_switched_off() -> None:
    gateway = FakeGateway(['{"search": "grant"}', "never used"])
    calls: list[str] = []
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: calls.append(query) or [],
        search_enabled=False,
    )
    controller.send("find a grant")
    assert calls == []
    assert len(gateway.requests) == 1

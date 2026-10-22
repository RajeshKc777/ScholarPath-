"""Web search for the chat: parsing, guards and the turn flow (G136)."""

from __future__ import annotations

import json

from scholarpath.chat_context import catalog_hits
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
    # ".org" is a generic registry, not proof: a scholarship body has to be
    # trusted by the student (search.trusted_domains). With nothing trusted
    # and nothing official, the page order is kept.
    assert [result.url for result in results] == [
        "https://blog.example.com/scholarship",
        "https://www.chevening.org/scholarships",
    ]
    assert not results[0].official_looking
    block = format_results("uk scholarship", results)
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
    """With the switch off no search runs, and the model is told why."""
    gateway = FakeGateway(['{"search": "grant"}', "I could not check live pages."])
    calls: list[str] = []
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: calls.append(query) or [],
        search_enabled=False,
    )
    controller.send("find a grant")
    assert calls == [], "no search may run while the switch is off"
    assert len(gateway.requests) == 2, "the model is asked again without results"
    assert "switched off" in gateway.requests[1].messages[-1].content.casefold()
    assert controller.history[-1].error is False


# -- G179: the app can search, so the model must not say it cannot ---------------


def test_a_refusal_to_search_is_asked_once_more() -> None:
    """A "I cannot browse the web" reply is the model refusing, not the app."""
    gateway = FakeGateway(
        [
            "I can't browse the web, so I cannot check the current deadlines.",
            '{"search": "korea scholarship 2027"}',
            "The government portal is studyinkorea.go.kr.",
        ]
    )
    calls: list[str] = []
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: (
            calls.append(query)
            or [SearchResult(title="T", url="https://www.studyinkorea.go.kr/x")]
        ),
    )
    controller.send("what scholarships are open in korea?")

    assert calls == ["korea scholarship 2027"], "the search ran after the retry"
    assert len(gateway.requests) == 3, "one refusal, one retry, one answer"
    retry = gateway.requests[1].messages[-1].content
    assert "never say that you cannot search" in retry.casefold()
    assert controller.history[-1].text.startswith("The government portal")


def test_the_refusal_is_not_retried_when_the_search_is_off() -> None:
    gateway = FakeGateway(["I can't browse the web, sorry."])
    calls: list[str] = []
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: calls.append(query) or [],
        search_enabled=False,
    )
    controller.send("what scholarships are open in korea?")

    assert calls == []
    assert len(gateway.requests) == 1, "no retry while the switch is off"


def test_a_refusal_is_retried_only_once() -> None:
    gateway = FakeGateway(["I can't browse the web."])
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: [],
    )
    controller.send("what is open in korea?")

    assert len(gateway.requests) == 2, "one retry, no more"


def test_an_ordinary_reply_is_not_retried() -> None:
    gateway = FakeGateway(["The web results say the deadline is in March."])
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: [],
    )
    controller.send("what is open in korea?")

    assert len(gateway.requests) == 1


# -- G182: the verified catalog comes before the web results ---------------------

CATALOG_RECORD = {
    "id": 1,
    "title": "DAAD Development-Related Postgraduate Courses",
    "provider": "DAAD",
    "provider_domain": "daad.de",
    "level": "Master's",
    "countries": "Germany",
    "fields_of_study": "Development Studies",
    "funding_type": "Full funding",
    "amount_text": "EUR 1,000 per month",
    "deadline_text": "15 August",
    "deadline_date": "2027-08-15",
    "language_req": "English",
    "apply_url": "https://www.daad.de/en/apply",
    "final_url": "https://www.daad.de/en/graduate-scholarships",
    "retrieved_at": "2026-10-20T09:00:00+00:00",
    "data": {"last_checked_at": "2026-10-21T08:00:00+00:00"},
}


def test_the_catalog_block_reaches_the_model_with_its_provenance() -> None:
    gateway = FakeGateway(["Here is what I found."])
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: [],
        catalog=lambda question: catalog_hits([CATALOG_RECORD], question),
    )
    controller.send("is there a daad scholarship for germany?")

    sent = " ".join(message.content for message in gateway.requests[0].messages)
    assert "verified in your catalog" in sent.casefold()
    assert "https://www.daad.de/en/graduate-scholarships" in sent
    assert "2026-10-21" in sent


def test_the_catalog_comes_before_the_web_results() -> None:
    gateway = FakeGateway(
        [
            '{"search": "germany scholarship 2027"}',
            "The DAAD page is the one to read.",
        ]
    )
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: [
            SearchResult(title="Blog", url="https://blog.example.com/x", snippet="s")
        ],
        catalog=lambda question: catalog_hits([CATALOG_RECORD], question),
    )
    controller.send("is there a daad scholarship for germany?")

    messages = gateway.requests[1].messages
    catalog_index = next(
        index
        for index, message in enumerate(messages)
        if "verified in your catalog" in message.content.casefold()
    )
    web_index = next(
        index
        for index, message in enumerate(messages)
        if "Web search results" in message.content
    )
    assert catalog_index < web_index, "the verified catalog goes first"


def test_web_results_are_marked_as_unverified_leads() -> None:
    block = format_results(
        "germany scholarship",
        [SearchResult(title="Blog", url="https://blog.example.com/x", snippet="s")],
    )
    assert "unverified lead" in block.casefold()
    assert "not an official domain" in block

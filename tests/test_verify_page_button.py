"""Verify this page: the button the chat offers on its own links (G184).

An official-looking link in a reply gets a button. Pressing it opens the
Scholarship Pages page with that address and runs the existing read-and-
verify flow, which ends with a card that can be saved to the catalog. The
tests use a fake fetch: no network.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFrame, QToolButton

from scholarpath.chat_context import official_links
from scholarpath.gateway.base import ChatResponse, ModelGateway
from scholarpath.research import build_scholarship_draft
from scholarpath.sources import Page
from scholarpath.storage import Database
from scholarpath.ui.chat_controller import Turn
from scholarpath.ui.main_window import TurnWidget
from scholarpath.ui.research_page import ResearchPage

PAGE_TEXT = """BEST GRANT 2027 - Official Programme Page
Host country: Netherlands.
Tuition fees covered in full. Monthly allowance of EUR 1 150.
Application deadline: 1 February 2027.
Required: motivation letter and two recommendations."""


def make_page(url: str = "https://example.edu/grant") -> Page:
    return Page(
        requested_url=url,
        final_url=url,
        title="BEST GRANT 2027",
        text=PAGE_TEXT,
        fetched_at="2026-10-22T10:00:00",
        sha256="abc123",
    )


class FakeGateway(ModelGateway):
    name = "fake"

    def complete(self, request):  # noqa: ANN001 - the gateway API
        fields = {
            "title": "BEST GRANT 2027",
            "host_country": "Netherlands",
            "funding_coverage": "Tuition fees covered in full",
        }
        return ChatResponse(
            text="```json\n" + json.dumps({"fields": fields}) + "\n```",
            model="fake-model",
        )


def test_only_official_addresses_are_offered_for_verification() -> None:
    text = (
        "Check https://www.studyinkorea.go.kr/plan/scholarship.do and "
        "https://blog.example.com/post for the details."
    )
    links = official_links(text)

    assert links == ["https://www.studyinkorea.go.kr/plan/scholarship.do"]


def test_a_reply_with_an_official_link_gets_a_verify_button() -> None:
    asked: list[str] = []
    widget = TurnWidget(
        Turn(
            role="assistant",
            text="Start here: https://www.studyinkorea.go.kr/plan/scholarship.do",
        ),
        on_verify=asked.append,
    )
    buttons = [
        button
        for button in widget.findChildren(QToolButton)
        if button.objectName() == "VerifyLink"
    ]

    assert len(buttons) == 1
    assert buttons[0].text() == "Verify this page"
    buttons[0].click()
    assert asked == ["https://www.studyinkorea.go.kr/plan/scholarship.do"]


def test_a_reply_with_only_third_party_links_gets_no_button() -> None:
    asked: list[str] = []
    widget = TurnWidget(
        Turn(role="assistant", text="See https://blog.example.com/post"),
        on_verify=asked.append,
    )
    buttons = [
        button
        for button in widget.findChildren(QToolButton)
        if button.objectName() == "VerifyLink"
    ]

    assert buttons == []


def test_the_button_runs_the_read_and_verify_flow(monkeypatch, tmp_path) -> None:
    """The page is fetched, checked against the page, and offered for saving."""
    import scholarpath.ui.research_page as research_page

    page = make_page("https://www.studyinkorea.go.kr/plan/scholarship.do")
    draft = build_scholarship_draft(
        page,
        {
            "title": "BEST GRANT 2027",
            "host_country": "Netherlands",
            "funding_coverage": "Tuition fees covered in full",
        },
    )

    class FakeWorker(QObject):
        fetched = Signal(object, str)
        drafted = Signal(object, str)
        finished = Signal()

        def __init__(self, url, gateway, model) -> None:  # noqa: ANN001
            super().__init__()
            self.url = url

        def start(self) -> None:
            self.fetched.emit(page, "")
            self.drafted.emit(draft, "")
            self.finished.emit()

        def isRunning(self) -> bool:  # noqa: N802 - Qt API
            return False

    monkeypatch.setattr(research_page, "_VerifyWorker", FakeWorker)

    database = Database(tmp_path / "verify.db")
    try:
        page_widget = ResearchPage(database, FakeGateway(), "fake-model")
        page_widget.open_url("https://www.studyinkorea.go.kr/plan/scholarship.do")

        assert page_widget.url_input.text() == (
            "https://www.studyinkorea.go.kr/plan/scholarship.do"
        )
        cards = [
            widget
            for widget in page_widget.findChildren(QFrame)
            if widget.objectName() == "DocCard"
        ]
        assert cards, "the draft was shown, ready to be saved"
    finally:
        database.close()


def test_the_window_opens_the_page_on_the_scholarships_page(monkeypatch, tmp_path) -> None:
    """The button in a real window lands on the read-and-verify page."""
    import scholarpath.ui.main_window as main_window
    import scholarpath.ui.research_page as research_page
    from scholarpath.config import AppConfig
    from scholarpath.gateway.stub import StubGateway
    from scholarpath.ui.chat_controller import ChatController
    from scholarpath.ui.main_window import MainWindow

    class FakeWorker(QObject):
        fetched = Signal(object, str)
        drafted = Signal(object, str)
        finished = Signal()

        def __init__(self, url, gateway, model) -> None:  # noqa: ANN001
            super().__init__()
            self.url = url

        def start(self) -> None:
            self.fetched.emit(make_page(self.url), "")
            self.finished.emit()

        def isRunning(self) -> bool:  # noqa: N802 - Qt API
            return False

    monkeypatch.setattr(research_page, "_VerifyWorker", FakeWorker)
    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "verify.db")

    window = MainWindow(ChatController(StubGateway(), "stub"), AppConfig())
    try:
        window._verify_from_chat("https://www.studyinkorea.go.kr/plan/scholarship.do")

        assert window._page_name == "research"
        assert window._research_page.url_input.text() == (
            "https://www.studyinkorea.go.kr/plan/scholarship.do"
        )
    finally:
        window._database.close()
        window.close()

"""Verify this page: the button the chat offers on its own links (G184, G186).

An official-looking link in a reply gets a button. Pressing it verifies the
page **in the chat**: the page is read, every proposed value is checked
word-for-word against it, the checked values and the ones the page does not
state are shown under the reply, and the record can be saved to the catalog
from there. The tests use a fake fetch: no network.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFrame, QLabel, QToolButton

from scholarpath.chat_context import official_links
from scholarpath.gateway.base import ChatResponse, ModelGateway
from scholarpath.research import build_scholarship_draft
from scholarpath.sources import Page
from scholarpath.storage import Database
from scholarpath.ui.chat_controller import Turn
from scholarpath.ui.chat_verify import VerifyPanel
from scholarpath.ui.main_window import TurnWidget
from scholarpath.ui.research_page import ResearchPage

PAGE_TEXT = """BEST GRANT 2027 - Official Programme Page
Host country: Netherlands.
Tuition fees covered in full. Monthly allowance of EUR 1 150.
Application deadline: 1 February 2027.
Required: motivation letter and two recommendations."""

URL = "https://www.studyinkorea.go.kr/plan/scholarship.do"


def make_page(url: str = URL) -> Page:
    return Page(
        requested_url=url,
        final_url=url,
        title="BEST GRANT 2027",
        text=PAGE_TEXT,
        fetched_at="2026-10-22T10:00:00",
        sha256="abc123",
    )


def make_draft(page: Page | None = None) -> object:
    """A draft with three values that are on the page and one that is not."""
    return build_scholarship_draft(
        page or make_page(),
        {
            "title": "BEST GRANT 2027",
            "host_country": "Netherlands",
            "funding_coverage": "Tuition fees covered in full",
            "stipend": "EUR 2,000 per month",
        },
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


def fake_worker(page: object | None, draft: object | None, error: str = ""):
    """A worker that answers at once, so the tests never touch the network."""

    class FakeWorker(QObject):
        fetched = Signal(object, str)
        drafted = Signal(object, str)
        finished = Signal()

        def __init__(self, url, gateway, model) -> None:  # noqa: ANN001
            super().__init__()
            self.url = url

        def start(self) -> None:
            if error:
                self.fetched.emit(None, error)
            else:
                self.fetched.emit(page, "")
                self.drafted.emit(draft, "")
            self.finished.emit()

        def isRunning(self) -> bool:  # noqa: N802 - Qt API
            return False

    return FakeWorker


def panel_text(panel: VerifyPanel) -> str:
    return " ".join(label.text() for label in panel.findChildren(QLabel))


def verify_buttons(widget: QFrame) -> list[QToolButton]:
    return [
        button
        for button in widget.findChildren(QToolButton)
        if button.objectName() == "VerifyLink"
    ]


def test_only_official_addresses_are_offered_for_verification() -> None:
    text = (
        "Check https://www.studyinkorea.go.kr/plan/scholarship.do and "
        "https://blog.example.com/post for the details."
    )
    links = official_links(text)

    assert links == [URL]


def test_a_reply_with_an_official_link_gets_a_verify_button() -> None:
    asked: list[str] = []
    widget = TurnWidget(
        Turn(role="assistant", text=f"Start here: {URL}"),
        on_verify=asked.append,
    )
    buttons = verify_buttons(widget)

    assert len(buttons) == 1
    assert buttons[0].text() == "Verify this page"
    buttons[0].click()
    assert asked == [URL]


def test_a_reply_with_only_third_party_links_gets_no_button() -> None:
    asked: list[str] = []
    widget = TurnWidget(
        Turn(role="assistant", text="See https://blog.example.com/post"),
        on_verify=asked.append,
    )

    assert verify_buttons(widget) == []


def test_pressing_the_button_opens_the_result_under_the_reply() -> None:
    """The verification happens in the chat, not on another page (G186)."""
    panel = QLabel("checked")
    widget = TurnWidget(
        Turn(role="assistant", text=f"Start here: {URL}"),
        on_verify=lambda url: panel,
    )
    buttons = verify_buttons(widget)

    buttons[0].click()

    assert widget.isAncestorOf(panel), "the result sits inside the reply"
    assert buttons[0].isEnabled() is False, "the button is not pressed twice"


def test_the_button_says_when_the_page_could_not_be_checked(
    monkeypatch, tmp_path
) -> None:
    import scholarpath.ui.chat_verify as chat_verify

    monkeypatch.setattr(
        chat_verify,
        "VerifyWorker",
        fake_worker(None, None, error="the address refused the connection"),
    )

    database = Database(tmp_path / "chat.db")
    try:
        panel = VerifyPanel(URL, FakeGateway(), "fake-model", database)
        widget = TurnWidget(
            Turn(role="assistant", text=f"Start here: {URL}"),
            on_verify=lambda url: panel,
        )
        buttons = verify_buttons(widget)

        buttons[0].click()

        assert buttons[0].text() == "Could not check"
    finally:
        database.close()


def test_the_button_runs_the_read_and_verify_flow(monkeypatch, tmp_path) -> None:
    """The Scholarship Pages page still reads the page and offers the draft."""
    import scholarpath.ui.research_page as research_page

    page = make_page()
    draft = make_draft(page)

    monkeypatch.setattr(research_page, "_VerifyWorker", fake_worker(page, draft))

    database = Database(tmp_path / "verify.db")
    try:
        page_widget = ResearchPage(database, FakeGateway(), "fake-model")
        page_widget.open_url(URL)

        assert page_widget.url_input.text() == URL
        cards = [
            widget
            for widget in page_widget.findChildren(QFrame)
            if widget.objectName() == "DocCard"
        ]
        assert cards, "the draft was shown, ready to be saved"
    finally:
        database.close()


# -- G186: the verification happens in the chat ---------------------------------


def test_the_panel_shows_what_the_page_states_and_what_it_does_not(
    monkeypatch, tmp_path
) -> None:
    import scholarpath.ui.chat_verify as chat_verify

    page = make_page()
    draft = make_draft(page)
    monkeypatch.setattr(
        chat_verify, "VerifyWorker", fake_worker(page, draft)
    )

    database = Database(tmp_path / "chat.db")
    try:
        panel = VerifyPanel(URL, FakeGateway(), "fake-model", database)
        text = panel_text(panel)

        assert "appear word-for-word on the page" in text
        assert "Host country: Netherlands" in text
        assert "not on the page word-for-word" in text
        assert "EUR 2,000 per month" not in text
    finally:
        database.close()


def test_saving_from_the_chat_stores_only_the_checked_values(
    monkeypatch, tmp_path
) -> None:
    import scholarpath.ui.chat_verify as chat_verify

    page = make_page()
    draft = make_draft(page)
    monkeypatch.setattr(
        chat_verify, "VerifyWorker", fake_worker(page, draft)
    )

    database = Database(tmp_path / "chat.db")
    try:
        panel = VerifyPanel(URL, FakeGateway(), "fake-model", database)
        panel._on_save()  # noqa: SLF001 - the button does exactly this

        rows = list(database.scholarships())
        assert len(rows) == 1
        values = rows[0]["data"]["values"]
        assert values["host_country"] == "Netherlands"
        assert "stipend" not in values, "a value the page does not state is not saved"
        assert rows[0]["final_url"] == URL
        assert rows[0]["page_sha256"] == "abc123"
        assert "Saved 3 value(s)" in panel_text(panel)
    finally:
        database.close()


def test_a_page_that_cannot_be_read_says_so_and_saves_nothing(
    monkeypatch, tmp_path
) -> None:
    import scholarpath.ui.chat_verify as chat_verify

    monkeypatch.setattr(
        chat_verify,
        "VerifyWorker",
        fake_worker(None, None, error="the address refused the connection"),
    )

    database = Database(tmp_path / "chat.db")
    try:
        panel = VerifyPanel(URL, FakeGateway(), "fake-model", database)
        text = panel_text(panel)

        assert "Could not read the page" in text
        assert "nothing was saved" in text.casefold()
        assert list(database.scholarships()) == []
    finally:
        database.close()


def test_the_window_verifies_the_page_in_the_chat(monkeypatch, tmp_path) -> None:
    """The student stays in the conversation; the result opens under the reply."""
    import scholarpath.ui.chat_verify as chat_verify
    import scholarpath.ui.main_window as main_window
    from scholarpath.config import AppConfig
    from scholarpath.gateway.stub import StubGateway
    from scholarpath.ui.chat_controller import ChatController
    from scholarpath.ui.main_window import MainWindow

    page = make_page()
    draft = make_draft(page)
    monkeypatch.setattr(
        chat_verify, "VerifyWorker", fake_worker(page, draft)
    )
    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "verify.db")

    window = MainWindow(ChatController(StubGateway(), "stub"), AppConfig())
    try:
        panel = window._verify_from_chat(URL)

        assert isinstance(panel, VerifyPanel)
        assert window._page_name == "chat", "the chat did not send the student away"
        assert "Host country: Netherlands" in panel_text(panel)
    finally:
        window._database.close()
        window.close()

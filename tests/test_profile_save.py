"""Saving the profile must be visible, and the side card must never be stale (G137)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from scholarpath.storage import Database
from scholarpath.ui.profile_page import ProfilePage


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _page(database: Database) -> ProfilePage:
    page = ProfilePage(database)
    return page


def test_saving_reports_what_happened(app: QApplication, tmp_path) -> None:
    database = Database(tmp_path / "profile.db")
    page = _page(database)
    page._name.setText("Rajesh Katuwal")
    page._nationality.setText("Nepali")
    page._institution.setText("London Metropolitan University")
    page._year.setText("2025")
    page._gpa.setText("3.6")

    before = page._saved_label.text()
    page._on_save()
    after = page._saved_label.text()

    assert after, "a save must say something"
    assert after != before, "a save must visibly change the message"
    assert "Saved locally" in after
    assert "%" in after
    database.close()


def test_saving_really_writes_the_values(app: QApplication, tmp_path) -> None:
    database = Database(tmp_path / "profile.db")
    page = _page(database)
    page._name.setText("Rajesh Katuwal")
    page._on_save()

    record = database.load_profile()
    assert record
    assert record["data"]["student_name"] == "Rajesh Katuwal"
    database.close()


def test_a_failed_save_is_reported_not_hidden(app: QApplication, tmp_path) -> None:
    database = Database(tmp_path / "profile.db")

    def broken(payload) -> None:  # noqa: ANN001
        raise OSError("disk is full")

    database.save_profile = broken  # type: ignore[method-assign]
    page = _page(database)
    page._name.setText("Someone")
    page._on_save()

    assert "could not be saved" in page._saved_label.text().casefold()
    database.close()


def test_the_callback_runs_after_a_save(app: QApplication, tmp_path) -> None:
    database = Database(tmp_path / "profile.db")
    calls: list[int] = []
    page = ProfilePage(database, on_saved=lambda: calls.append(1))
    page._name.setText("Someone")
    page._on_save()
    assert calls == [1]
    database.close()


def test_a_broken_callback_does_not_undo_the_save(app: QApplication, tmp_path) -> None:
    database = Database(tmp_path / "profile.db")

    def broken() -> None:
        raise RuntimeError("the panel is broken")

    page = ProfilePage(database, on_saved=broken)
    page._name.setText("Someone")
    page._on_save()

    assert "Saved locally" in page._saved_label.text()
    assert "could not be refreshed" in page._saved_label.text()
    record = database.load_profile()
    assert record and record["data"]["student_name"] == "Someone"
    database.close()


def test_the_side_card_mirrors_the_saved_profile(app: QApplication, tmp_path, monkeypatch) -> None:
    """The right-hand card must never keep saying 'Not set up yet'."""
    import scholarpath.ui.main_window as main_window
    from scholarpath.config import load_config
    from scholarpath.gateway.base import ChatResponse
    from scholarpath.ui.chat_controller import ChatController

    class FakeGateway:
        name = "fake-local"

        def complete(self, request):  # noqa: ANN001
            return ChatResponse(text="ok", model="m")

    monkeypatch.setattr(main_window, "database_path", lambda: tmp_path / "window.db")
    window = main_window.MainWindow(ChatController(FakeGateway()), load_config(None))
    try:
        window._profile_page._name.setText("Rajesh Katuwal")
        window._profile_page._nationality.setText("Nepali")
        window._profile_page._on_save()

        assert "Rajesh Katuwal" in window._profile_name.text()
        assert "Not set up yet" not in window._profile_name.text()
        assert "% complete" in window._profile_progress.text()
        assert "no profile data yet" not in window._profile_progress.text()
    finally:
        window._database.close()
        window.close()

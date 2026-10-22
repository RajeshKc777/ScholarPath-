"""Privacy switches: on by default, gated, and changeable from Settings (G140, G171)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from scholarpath.config import AppConfig, PrivacyConfig, load_config
from scholarpath.gateway.base import ChatResponse
from scholarpath.ui.chat_controller import ChatController
from scholarpath.ui.main_window import MainWindow
from scholarpath.websearch import SearchResult


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_every_switch_is_on_by_default() -> None:
    privacy = AppConfig().privacy
    assert privacy.voice_stt is True
    assert privacy.voice_tts is True
    assert privacy.web_search is True


def test_a_config_file_can_turn_them_off(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "[privacy]\nvoice_stt = false\nvoice_tts = false\nweb_search = true\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.privacy.voice_stt is False
    assert config.privacy.voice_tts is False
    assert config.privacy.web_search is True


def test_an_unknown_privacy_key_is_rejected() -> None:
    with pytest.raises(Exception):
        PrivacyConfig(voice_transcription=True)  # type: ignore[call-arg]


class FakeGateway:
    name = "fake-local"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.requests = []

    def complete(self, request):  # noqa: ANN001
        self.requests.append(request)
        reply = self.replies[min(len(self.requests) - 1, len(self.replies) - 1)]
        return ChatResponse(text=reply, model="fake-model")


def test_search_does_not_run_when_it_is_switched_off() -> None:
    gateway = FakeGateway(['{"search": "uk scholarship"}', "I could not check it."])
    searched: list[str] = []
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: searched.append(query) or [],
        search_enabled=False,
    )
    controller.send("search scholarship in uk")

    assert searched == [], "no search may run while the switch is off"
    assert len(gateway.requests) == 2, "the model is asked again without results"
    follow_up = gateway.requests[1].messages[-1].content
    assert "switched off" in follow_up.casefold()
    assert "never claim to have searched" in follow_up.casefold()
    assert controller.history[-1].error is False


def test_the_model_is_told_up_front_that_search_is_off() -> None:
    gateway = FakeGateway(["A plain answer."])
    controller = ChatController(
        gateway, "fake-model", dispatch=lambda work: work(), search_enabled=False
    )
    controller.send("what is the deadline?")
    system_messages = [
        message.content
        for message in gateway.requests[0].messages
        if message.role == "system"
    ]
    assert any("switched off" in text.casefold() for text in system_messages)


def test_search_runs_when_it_is_switched_on() -> None:
    gateway = FakeGateway(['{"search": "uk scholarship"}', "Here is what I found."])
    searched: list[str] = []
    controller = ChatController(
        gateway,
        "fake-model",
        dispatch=lambda work: work(),
        searcher=lambda query: searched.append(query)
        or [SearchResult(title="T", url="https://example.org/x")],
        search_enabled=True,
    )
    controller.send("search scholarship in uk")
    assert searched == ["uk scholarship"]


def _window(app: QApplication, tmp_path, privacy: PrivacyConfig) -> MainWindow:
    import scholarpath.ui.main_window as main_window

    main_window.database_path = lambda: tmp_path / "privacy.db"
    config = AppConfig()
    config.privacy = privacy
    return MainWindow(ChatController(FakeGateway(["ok"]), "m"), config)


def test_the_mic_does_nothing_while_voice_input_is_off(app, tmp_path) -> None:
    window = _window(
        app,
        tmp_path,
        PrivacyConfig(voice_stt=False, voice_tts=True, web_search=True),
    )
    try:
        window._toggle_voice()
        worker = getattr(window, "_voice_worker", None)
        assert worker is None or not worker.isRunning()
        assert "Voice input is off" in (window._notice or "")
    finally:
        window._database.close()
        window.close()


def test_live_voice_stays_off_without_both_switches(app, tmp_path) -> None:
    window = _window(app, tmp_path, PrivacyConfig(voice_stt=True, voice_tts=False))
    try:
        window._toggle_voice_mode()
        assert not window._voice_mode_active()
        assert "spoken replies" in (window._notice or "").casefold()
    finally:
        window._database.close()
        window.close()

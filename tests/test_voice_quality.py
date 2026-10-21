"""Natural voice + sticky auto-scroll behaviour (G130)."""

from __future__ import annotations

from scholarpath.tts import (
    DEFAULT_NEURAL_VOICE,
    ENGINE_NEURAL,
    ENGINE_OFFLINE,
    NEURAL_VOICES,
    Speaker,
    engine_label,
)
from scholarpath.ui.main_window import should_stick_to_bottom


def test_engine_labels_are_student_facing() -> None:
    neural = engine_label(ENGINE_NEURAL)
    offline = engine_label(ENGINE_OFFLINE)
    assert "neural" in neural.lower()
    assert "offline" in offline.lower()
    assert "Error" not in neural and "0x" not in neural


def test_default_voice_is_a_known_neural_voice() -> None:
    assert DEFAULT_NEURAL_VOICE in NEURAL_VOICES
    assert all(name.startswith("en-US-") for name in NEURAL_VOICES)


def test_speaker_reports_the_engine_it_used() -> None:
    """With a fake engine, the speaker must say which engine spoke."""
    speaker = Speaker()
    engines: list[str] = []
    speaker.engine_changed.connect(engines.append)

    class FakeEngine:
        def say(self, text: str) -> None:
            pass

        def runAndWait(self) -> None:  # noqa: N802 - third-party API
            pass

        def stop(self) -> None:  # noqa: N802 - third-party API
            pass

    speaker._speak("hello", init=lambda: FakeEngine(), engine=ENGINE_OFFLINE)
    assert engines == [ENGINE_OFFLINE]
    assert speaker.engine_name == ENGINE_OFFLINE


def test_speaker_falls_back_to_the_offline_voice(monkeypatch) -> None:
    """A broken neural engine must still produce speech, not silence."""
    import scholarpath.tts as tts

    monkeypatch.setattr(tts, "_neural_available", lambda: True)

    def broken_neural(self, text: str) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(Speaker, "_speak_neural", broken_neural)

    spoken: list[str] = []

    class FakeEngine:
        def say(self, text: str) -> None:
            spoken.append(text)

        def runAndWait(self) -> None:  # noqa: N802 - third-party API
            pass

        def stop(self) -> None:  # noqa: N802 - third-party API
            pass

    speaker = Speaker()
    speaker._speak("fallback please", init=lambda: FakeEngine())
    assert spoken == ["fallback please"]
    assert speaker.engine_name == ENGINE_OFFLINE


def test_scroll_follows_only_when_at_the_bottom() -> None:
    assert should_stick_to_bottom(1000, 1000)
    assert should_stick_to_bottom(1000, 992)  # within the threshold
    assert not should_stick_to_bottom(1000, 900)  # student scrolled up
    assert not should_stick_to_bottom(1000, 0)

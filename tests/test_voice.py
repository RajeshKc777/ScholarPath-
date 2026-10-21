"""Voice-to-text module: availability, error mapping, callbacks (G124)."""

from __future__ import annotations

from types import SimpleNamespace

from scholarpath import voice
from scholarpath.voice import (
    LIBRARY_MISSING,
    MAX_LISTEN_SECONDS,
    NO_MICROPHONE,
    NOTHING_HEARD,
    SERVICE_UNREACHABLE,
    STOPPED,
    VoiceError,
    availability,
    listen_once,
)


def test_availability_without_the_library_is_honest(monkeypatch) -> None:
    monkeypatch.setattr(voice, "_sr", None)
    usable, reason = availability()
    assert not usable
    assert reason == LIBRARY_MISSING
    assert "stays off" in reason


def test_availability_without_a_microphone_is_honest(monkeypatch) -> None:
    fake = SimpleNamespace(
        Microphone=SimpleNamespace(list_microphone_names=lambda: [])
    )
    monkeypatch.setattr(voice, "_sr", fake)
    usable, reason = availability()
    assert not usable
    assert reason == NO_MICROPHONE


def test_availability_reports_a_usable_microphone(monkeypatch) -> None:
    fake = SimpleNamespace(
        Microphone=SimpleNamespace(
            list_microphone_names=lambda: ["Microphone Array (Realtek)"]
        )
    )
    monkeypatch.setattr(voice, "_sr", fake)
    usable, reason = availability()
    assert usable and reason == ""


def test_success_path_delivers_recognized_text(monkeypatch) -> None:
    monkeypatch.setattr(
        voice, "_record_and_transcribe", lambda seconds: "Apply for Chevening"
    )
    done: list[str] = []
    errors: list[str] = []
    listen_once(done.append, errors.append)
    assert done == ["Apply for Chevening"]
    assert not errors


def test_no_speech_maps_to_a_student_message(monkeypatch) -> None:
    def nothing(_seconds: float) -> str:
        raise VoiceError(NOTHING_HEARD)

    monkeypatch.setattr(voice, "_record_and_transcribe", nothing)
    done: list[str] = []
    errors: list[str] = []
    listen_once(done.append, errors.append)
    assert not done
    assert errors == [NOTHING_HEARD]


def test_crash_is_reported_and_cancel_is_not_an_error_message(monkeypatch) -> None:
    def crash(_seconds: float) -> str:
        raise RuntimeError("stream died")

    monkeypatch.setattr(voice, "_record_and_transcribe", crash)
    errors: list[str] = []
    listen_once(lambda _text: None, errors.append)
    assert errors and "unexpectedly" in errors[0]

    errors.clear()

    def crash_while_canceled(_seconds: float) -> str:
        voice._cancel_event.set()  # simulate a student stopping mid-capture
        raise RuntimeError("stream stopped by cancel")

    monkeypatch.setattr(voice, "_record_and_transcribe", crash_while_canceled)
    listen_once(lambda _text: None, errors.append)
    voice._cancel_event.clear()
    assert errors == [STOPPED]


def test_cancel_active_marks_the_capture_and_stops_sources() -> None:
    stopped: list[bool] = []

    class Source:
        def stop(self) -> None:
            stopped.append(True)

    source = Source()
    voice._register_active(source)
    try:
        voice.cancel_active()
        assert stopped == [True]
        assert voice._cancel_event.is_set()
    finally:
        voice._unregister_active(source)
        voice._cancel_event.clear()


def test_cancel_active_stops_the_microphone_stream() -> None:
    """`Microphone` has no stop(); the capture ends by stopping its stream."""

    class Stream:
        def __init__(self) -> None:
            self.stopped = False

        def stop_stream(self) -> None:
            self.stopped = True

    class Microphone:
        def __init__(self) -> None:
            self.stream = Stream()

    source = Microphone()
    voice._register_active(source)
    try:
        voice.cancel_active()
        assert source.stream.stopped
    finally:
        voice._unregister_active(source)
        voice._cancel_event.clear()


def test_cancel_active_survives_a_source_that_cannot_stop() -> None:
    class Stubborn:
        stream = None

    source = Stubborn()
    voice._register_active(source)
    try:
        voice.cancel_active()  # must never raise
        assert voice._cancel_event.is_set()
    finally:
        voice._unregister_active(source)
        voice._cancel_event.clear()


def test_messages_are_student_facing() -> None:
    for message in (NOTHING_HEARD, NO_MICROPHONE, SERVICE_UNREACHABLE, LIBRARY_MISSING):
        assert message and "Error" not in message and "0x" not in message


def test_max_listen_cap_is_sane() -> None:
    assert 5 <= MAX_LISTEN_SECONDS <= 120


def test_voice_error_carries_only_the_student_message() -> None:
    error = VoiceError("plain reason")
    assert str(error) == "plain reason"
    assert error.student_message == "plain reason"

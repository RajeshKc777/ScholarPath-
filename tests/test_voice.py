"""Voice-to-text module: availability, error mapping, callbacks (G124)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

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
        voice, "_record_and_transcribe", lambda seconds, **_kwargs: "Apply for Chevening"
    )
    done: list[str] = []
    errors: list[str] = []
    listen_once(done.append, errors.append)
    assert done == ["Apply for Chevening"]
    assert not errors


def test_no_speech_maps_to_a_student_message(monkeypatch) -> None:
    def nothing(_seconds: float, **_kwargs) -> str:
        raise VoiceError(NOTHING_HEARD)

    monkeypatch.setattr(voice, "_record_and_transcribe", nothing)
    done: list[str] = []
    errors: list[str] = []
    listen_once(done.append, errors.append)
    assert not done
    assert errors == [NOTHING_HEARD]


def test_crash_is_reported_and_cancel_is_not_an_error_message(monkeypatch) -> None:
    def crash(_seconds: float, **_kwargs) -> str:
        raise RuntimeError("stream died")

    monkeypatch.setattr(voice, "_record_and_transcribe", crash)
    errors: list[str] = []
    listen_once(lambda _text: None, errors.append)
    assert errors and "unexpectedly" in errors[0]

    errors.clear()

    def crash_while_canceled(_seconds: float, **_kwargs) -> str:
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


# -- diagnosis: numbers, never words (G174) ----------------------------------


class _FakeAudio:
    sample_rate = 16000
    sample_width = 2

    def __init__(self, seconds: float = 2.0) -> None:
        self.frame_data = b"\x00" * int(
            self.sample_rate * self.sample_width * seconds
        )


class _FakeRecognizer:
    def __init__(self, result=None, threshold: float = 300.0) -> None:
        self.energy_threshold = threshold
        self.result = (
            {"alternative": [{"transcript": "find scholarships in Germany"}]}
            if result is None
            else result
        )
        self.languages: list[str] = []
        self.show_all: list[bool] = []
        self.listen_args: list[dict] = []

    def adjust_for_ambient_noise(self, source, duration: float = 0.25) -> None:
        pass

    def listen(self, source, timeout=None, phrase_time_limit=None):
        self.listen_args.append(
            {"timeout": timeout, "phrase_time_limit": phrase_time_limit}
        )
        return _FakeAudio()

    def recognize_google(self, audio, language: str = "en-US", show_all: bool = False):
        self.languages.append(language)
        self.show_all.append(show_all)
        return self.result


class _FakeMicrophone:
    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _fake_library(recognizer) -> SimpleNamespace:
    import speech_recognition as sr

    return SimpleNamespace(
        Recognizer=lambda: recognizer,
        Microphone=_FakeMicrophone,
        WaitTimeoutError=sr.WaitTimeoutError,
        UnknownValueError=sr.UnknownValueError,
        RequestError=sr.RequestError,
    )


def test_capture_stats_are_numbers_only(monkeypatch, caplog) -> None:
    recognizer = _FakeRecognizer()
    monkeypatch.setattr(voice, "_sr", _fake_library(recognizer))
    seen: list[voice.CaptureStats] = []

    with caplog.at_level(logging.INFO, logger="scholarpath.voice"):
        text = voice._record_and_transcribe(
            12.0,
            language="en-IN",
            is_speaking=lambda: True,
            on_stats=seen.append,
        )

    assert text == "find scholarships in Germany"
    assert len(seen) == 1
    stats = seen[0]
    assert stats.engine == "google"
    assert stats.language == "en-IN"
    assert stats.duration_s >= 0.0
    assert stats.audio_s == pytest.approx(2.0)
    assert stats.reason == "silence"
    assert stats.tts_playing is True
    assert stats.chars == len(text)
    assert stats.confidence is None

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "voice event=capture_start" in logged
    assert "voice event=capture_end" in logged
    assert "voice event=transcribe_done" in logged
    assert "find scholarships" not in logged


def test_google_confidence_is_kept_when_the_service_sends_it(monkeypatch) -> None:
    recognizer = _FakeRecognizer(
        result={"alternative": [{"transcript": "hello", "confidence": 0.87}]}
    )
    monkeypatch.setattr(voice, "_sr", _fake_library(recognizer))

    text, confidence = voice._transcribe_google(recognizer, _FakeAudio(), "en-GB")

    assert text == "hello"
    assert confidence == pytest.approx(0.87)
    assert recognizer.show_all == [True]
    assert recognizer.languages == ["en-GB"]


def test_a_start_timeout_reports_its_reason(monkeypatch) -> None:
    recognizer = _FakeRecognizer()
    library = _fake_library(recognizer)

    def timeout(*_args, **_kwargs):
        raise library.WaitTimeoutError()

    recognizer.listen = timeout
    monkeypatch.setattr(voice, "_sr", library)
    seen: list[voice.CaptureStats] = []

    with pytest.raises(VoiceError):
        voice._record_and_transcribe(5.0, on_stats=seen.append)

    assert seen and seen[0].reason == "start_timeout"
    assert seen[0].chars == 0


def test_listen_once_passes_the_diagnostic_arguments(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake(seconds, **kwargs):
        calls["seconds"] = seconds
        calls.update(kwargs)
        return "heard"

    monkeypatch.setattr(voice, "_record_and_transcribe", fake)
    done: list[str] = []

    voice.listen_once(
        done.append,
        lambda _message: None,
        9.0,
        language="en-GB",
        is_speaking=lambda: False,
        on_stats=lambda _stats: None,
    )

    assert done == ["heard"]
    assert calls["seconds"] == 9.0
    assert calls["language"] == "en-GB"
    assert calls["is_speaking"]() is False

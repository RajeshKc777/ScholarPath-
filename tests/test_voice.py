"""Voice input module: availability, status mapping, honest errors (G123)."""

from __future__ import annotations

from scholarpath import voice
from scholarpath.voice import (
    MAX_LISTEN_SECONDS,
    VoiceError,
    _student_message_for_status,
    availability,
    listen_once,
)


def test_availability_reports_the_windows_toggle_honestly(monkeypatch) -> None:
    monkeypatch.setattr(voice, "_online_speech_enabled", lambda: False)
    usable, reason = availability()
    assert not usable
    assert "Online speech recognition" in reason

    monkeypatch.setattr(voice, "_online_speech_enabled", lambda: True)
    if _engine_present():
        usable, reason = availability()
        assert usable and reason == ""


def _engine_present() -> bool:
    try:
        import winsdk  # noqa: F401
        import winsdk.windows.media.speechrecognition  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def test_toggle_probe_is_read_only_and_swallows_errors(monkeypatch) -> None:
    def boom(*args: object) -> None:
        raise OSError("reg closed")

    import winreg

    monkeypatch.setattr(winreg, "OpenKey", boom)
    assert voice._online_speech_enabled() is False


def test_status_messages_are_student_facing() -> None:
    for name in (
        "PRIVACY_DECLINED",
        "MICROPHONE_UNAVAILABLE",
        "AUDIO_QUALITY_FAILURE",
        "NETWORK_FAILURE",
        "TIMEOUT_EXCEEDED",
        "USER_CANCELED",
        "UNKNOWN",
    ):
        message = _student_message_for_status(name, "")
        assert message and "Error" not in message and "0x" not in message


def test_platform_error_is_reported_verbatim_when_status_is_blank() -> None:
    message = _student_message_for_status("", "mic busy")
    assert "mic busy" in message


def test_listen_once_reports_the_error_to_the_callback() -> None:
    # A capture that cannot possibly succeed (immediate cap, no speech) must
    # surface through the error callback, never raise.
    done: list[str] = []
    errors: list[str] = []
    listen_once(done.append, errors.append, max_seconds=0.001)
    assert not done, "no recognized text can exist in an immediate test"
    assert errors, "the failure must surface through the error callback"


def test_max_listen_cap_is_sane() -> None:
    assert 5 <= MAX_LISTEN_SECONDS <= 120


def test_voice_error_carries_only_the_student_message() -> None:
    error = VoiceError("plain reason")
    assert str(error) == "plain reason"
    assert error.student_message == "plain reason"

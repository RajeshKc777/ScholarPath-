"""Voice-to-text input (G124): the Python SpeechRecognition library.

Design decisions (goals.md §19j):
- One click records from the default microphone; end-silence stops the
  capture, a second click stops early. The recognized words are returned as
  plain text for the composer - the student reviews them before sending.
- Transcription uses the library's free `recognize_google` engine: the short
  audio clip is sent to Google's speech service (no API key, needs an
  internet connection). The UI copy says exactly that; nothing claims the
  audio is understood locally.
- There is no Windows speech toggle and no model download; capture goes
  through PyAudio, the library's own audio layer.
- Every failure becomes a plain-language student message (no microphone, no
  speech, service/network problem, timeouts). No silent failure, no
  fabricated text.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger("scholarpath.voice")

MAX_LISTEN_SECONDS = 45.0
# How long to wait for the student to start speaking before giving up.
START_TIMEOUT = 15.0

try:  # optional at import time: the UI degrades honestly when missing
    import speech_recognition as _sr
except Exception:  # noqa: BLE001 - never crash the app at import
    _sr = None


class VoiceError(Exception):
    """Speech recognition failed with a student-facing reason message."""

    def __init__(self, student_message: str) -> None:
        super().__init__(student_message)
        self.student_message = student_message


NOTHING_HEARD = "Nothing was heard. Click the mic and try again."
NO_MICROPHONE = (
    "No microphone is available to this app. Check Windows microphone "
    "permissions (Settings \u2192 Privacy \u2192 Microphone)."
)
SERVICE_UNREACHABLE = (
    "The speech service could not be reached. Check the internet connection "
    "and try again."
)
LIBRARY_MISSING = (
    "The speech recognition library is not installed in this environment. "
    "Voice input stays off; typing still works."
)
STOPPED = "Voice input was stopped."


def availability() -> tuple[bool, str]:
    """(usable, reason) - an honest answer, never a silent flag."""
    if _sr is None:
        return False, LIBRARY_MISSING
    try:
        names = _sr.Microphone.list_microphone_names()
    except Exception as exc:  # noqa: BLE001 - any probe failure is reportable
        logger.info("microphone probe failed: %s", exc)
        return False, (
            "No usable microphone was found on this device. Voice input "
            "stays off; typing still works."
        )
    if not names:
        return False, NO_MICROPHONE
    return True, ""


_active_lock = threading.Lock()
_active_sources: list[object] = []
_cancel_event = threading.Event()


def _register_active(source: object) -> None:
    with _active_lock:
        _active_sources.append(source)


def _unregister_active(source: object) -> None:
    with _active_lock:
        if source in _active_sources:
            _active_sources.remove(source)


def _stop_source(source: object) -> None:
    """End a capture in progress.

    `speech_recognition.Microphone` has no `stop()`; the only way to break
    `Recognizer.listen()` is to stop its PyAudio stream, which makes the
    blocking read return. Sources that do expose `stop()` still work.
    """
    stream = getattr(source, "stream", None)
    if stream is not None:
        try:
            stream.stop_stream()
            return
        except Exception as exc:  # noqa: BLE001 - fall through to stop()
            logger.info("voice cancel (stream) failed: %s", exc)
    stop = getattr(source, "stop", None)
    if callable(stop):
        try:
            stop()
        except Exception as exc:  # noqa: BLE001 - the listen timeout still holds
            logger.info("voice cancel failed: %s", exc)


def cancel_active() -> None:
    """Stop a running capture (called from the UI thread)."""
    _cancel_event.set()
    with _active_lock:
        sources = list(_active_sources)
    for source in sources:
        _stop_source(source)


def _record_and_transcribe(max_seconds: float) -> str:
    recognizer = _sr.Recognizer()
    with _sr.Microphone() as source:
        _register_active(source)
        try:
            recognizer.adjust_for_ambient_noise(source, duration=0.25)
            audio = recognizer.listen(
                source,
                timeout=START_TIMEOUT,
                phrase_time_limit=min(max_seconds, MAX_LISTEN_SECONDS),
            )
        except _sr.WaitTimeoutError:
            raise VoiceError(NOTHING_HEARD) from None
        finally:
            _unregister_active(source)
    try:
        return recognizer.recognize_google(audio, language="en-US")
    except _sr.UnknownValueError:
        raise VoiceError(NOTHING_HEARD) from None
    except _sr.RequestError as exc:
        logger.info("speech service error: %s", exc)
        raise VoiceError(SERVICE_UNREACHABLE) from None


def listen_once(
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
    max_seconds: float = MAX_LISTEN_SECONDS,
) -> None:
    """Run one capture + transcription synchronously on the calling thread.

    Designed to be called from a `QThread.run()`: the UI stays live while the
    microphone blocks here. `cancel_active()` ends the wait early and reports
    the stop through `on_error`.
    """
    _cancel_event.clear()
    try:
        text = _record_and_transcribe(max_seconds)
    except VoiceError as exc:
        on_error(exc.student_message)
        return
    except Exception:  # noqa: BLE001 - voice must never crash the app
        logger.exception("voice capture crashed")
        on_error(STOPPED if _cancel_event.is_set() else "Voice input failed unexpectedly. Try again.")
        return
    on_done(text)

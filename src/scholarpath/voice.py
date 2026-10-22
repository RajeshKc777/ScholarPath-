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
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger("scholarpath.voice")

MAX_LISTEN_SECONDS = 45.0
# How long to wait for the student to start speaking before giving up.
START_TIMEOUT = 15.0
# The language asked of the speech service. Phase 2 makes this a setting.
DEFAULT_LANGUAGE = "en-US"

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


@dataclass(frozen=True)
class CaptureStats:
    """Numbers about one capture and transcription - never audio or words.

    Live voice diagnosis (G174) needs to know *how* a clip ended and whether
    the reply was still playing, without putting the student's words into the
    log. `chars` proves a transcript existed; the text itself never leaves the
    caller.
    """

    engine: str = "google"
    language: str = DEFAULT_LANGUAGE
    duration_s: float = 0.0  # wall time spent inside Recognizer.listen()
    audio_s: float = 0.0  # length of the recorded clip
    reason: str = "unknown"  # silence / phrase_limit / start_timeout / stopped / error
    tts_playing: bool = False
    energy_threshold: float = 0.0
    confidence: float | None = None
    chars: int = 0



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


def _clip_seconds(audio: object) -> float:
    """Length of a recorded clip, from its frames (0 when not measurable)."""
    try:
        rate = float(getattr(audio, "sample_rate", 0) or 0)
        width = float(getattr(audio, "sample_width", 0) or 0)
        frames = float(len(getattr(audio, "frame_data", b"")))
    except Exception:  # noqa: BLE001 - measuring is diagnostics, not a duty
        return 0.0
    if rate <= 0 or width <= 0:
        return 0.0
    return frames / (rate * width)


def _transcribe_google(
    recognizer: object, audio: object, language: str
) -> tuple[str, float | None]:
    """(text, confidence). Confidence stays None when Google does not send one.

    `show_all=True` is deliberate: `with_confidence=True` invents a 0.5 when
    the service omits the field, and a made-up confidence is worse than none.
    """
    started = time.monotonic()
    try:
        result = recognizer.recognize_google(  # type: ignore[attr-defined]
            audio, language=language, show_all=True
        )
    except _sr.UnknownValueError:
        logger.info(
            "voice event=transcribe_error engine=google language=%s detail=unknown_value",
            language,
        )
        raise VoiceError(NOTHING_HEARD) from None
    except _sr.RequestError:
        logger.info(
            "voice event=transcribe_error engine=google language=%s detail=request_error",
            language,
        )
        raise VoiceError(SERVICE_UNREACHABLE) from None

    text = ""
    confidence: float | None = None
    if isinstance(result, dict):
        alternatives = result.get("alternative") or []
        if alternatives and isinstance(alternatives[0], dict):
            text = str(alternatives[0].get("transcript") or "").strip()
            raw = alternatives[0].get("confidence")
            if isinstance(raw, (int, float)):
                confidence = float(raw)
    elif isinstance(result, str):
        text = result.strip()

    if not text:
        logger.info(
            "voice event=transcribe_error engine=google language=%s detail=empty",
            language,
        )
        raise VoiceError(NOTHING_HEARD)
    logger.info(
        "voice event=transcribe_done engine=google language=%s chars=%d "
        "confidence=%s elapsed_s=%.2f",
        language,
        len(text),
        "none" if confidence is None else f"{confidence:.2f}",
        time.monotonic() - started,
    )
    return text, confidence


def _record_and_transcribe(
    max_seconds: float,
    *,
    language: str = DEFAULT_LANGUAGE,
    start_timeout: float = START_TIMEOUT,
    is_speaking: Callable[[], bool] | None = None,
    on_stats: Callable[[CaptureStats], None] | None = None,
) -> str:
    recognizer = _sr.Recognizer()
    limit = min(max_seconds, MAX_LISTEN_SECONDS)
    playing_at_start = bool(is_speaking()) if is_speaking else False
    logger.info(
        "voice event=capture_start engine=google language=%s max_seconds=%.1f "
        "start_timeout_s=%.1f tts_playing=%s",
        language,
        limit,
        start_timeout,
        playing_at_start,
    )

    stats: dict[str, object] = {
        "engine": "google",
        "language": language,
        "duration_s": 0.0,
        "audio_s": 0.0,
        "reason": "error",
        "tts_playing": playing_at_start,
        "energy_threshold": 0.0,
        "confidence": None,
        "chars": 0,
    }
    # A reply can start and end *inside* one capture, so sampling only the
    # boundaries would miss it. A tiny watcher records whether TTS was alive
    # at any point while the microphone was open (G174).
    playing_during = {"value": playing_at_start}
    stop_watching = threading.Event()

    def watch_speech() -> None:
        while not stop_watching.wait(0.1):
            try:
                if is_speaking is not None and is_speaking():
                    playing_during["value"] = True
            except Exception:  # noqa: BLE001 - a probe must not break a capture
                return

    watcher = (
        threading.Thread(target=watch_speech, daemon=True)
        if is_speaking is not None
        else None
    )
    if watcher is not None:
        watcher.start()
    try:
        with _sr.Microphone() as source:
            _register_active(source)
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.25)
                stats["energy_threshold"] = float(
                    getattr(recognizer, "energy_threshold", 0.0) or 0.0
                )
                started = time.monotonic()
                try:
                    audio = recognizer.listen(
                        source,
                        timeout=start_timeout,
                        phrase_time_limit=limit,
                    )
                finally:
                    stats["duration_s"] = time.monotonic() - started
                stats["audio_s"] = _clip_seconds(audio)
                stats["reason"] = (
                    "phrase_limit"
                    if float(stats["audio_s"]) >= limit - 0.05
                    else "silence"
                )
            except _sr.WaitTimeoutError:
                stats["reason"] = "start_timeout"
                raise VoiceError(NOTHING_HEARD) from None
            except Exception:
                stats["reason"] = "stopped" if _cancel_event.is_set() else "error"
                raise
            finally:
                _unregister_active(source)
                stop_watching.set()
                playing_at_end = bool(is_speaking()) if is_speaking else False
                stats["tts_playing"] = (
                    playing_at_start
                    or playing_during["value"]
                    or playing_at_end
                )
                logger.info(
                    "voice event=capture_end duration_s=%.2f audio_s=%.2f "
                    "reason=%s tts_playing_start=%s tts_playing_during=%s "
                    "tts_playing_end=%s energy_threshold=%.0f",
                    float(stats["duration_s"]),
                    float(stats["audio_s"]),
                    stats["reason"],
                    playing_at_start,
                    playing_during["value"],
                    playing_at_end,
                    float(stats["energy_threshold"]),
                )
        text, confidence = _transcribe_google(recognizer, audio, language)
        stats["confidence"] = confidence
        stats["chars"] = len(text)
        return text
    finally:
        stop_watching.set()
        if watcher is not None:
            watcher.join(0.5)
        if on_stats is not None:
            try:
                on_stats(CaptureStats(**stats))  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001 - diagnostics must not break voice
                logger.info("voice event=stats_callback_failed")


def listen_once(
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
    max_seconds: float = MAX_LISTEN_SECONDS,
    *,
    language: str = DEFAULT_LANGUAGE,
    start_timeout: float = START_TIMEOUT,
    is_speaking: Callable[[], bool] | None = None,
    on_stats: Callable[[CaptureStats], None] | None = None,
) -> None:
    """Run one capture + transcription synchronously on the calling thread.

    Designed to be called from a `QThread.run()`: the UI stays live while the
    microphone blocks here. `cancel_active()` ends the wait early and reports
    the stop through `on_error`.

    `is_speaking` is read at the start and at the end of the capture so the
    log can say whether a reply was playing during it (G174). `on_stats`
    receives the same numbers, never the words.
    """
    _cancel_event.clear()
    try:
        text = _record_and_transcribe(
            max_seconds,
            language=language,
            start_timeout=start_timeout,
            is_speaking=is_speaking,
            on_stats=on_stats,
        )
    except VoiceError as exc:
        on_error(exc.student_message)
        return
    except Exception:  # noqa: BLE001 - voice must never crash the app
        logger.exception("voice capture crashed")
        on_error(STOPPED if _cancel_event.is_set() else "Voice input failed unexpectedly. Try again.")
        return
    on_done(text)

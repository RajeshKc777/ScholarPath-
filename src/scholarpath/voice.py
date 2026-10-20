"""On-device voice input (G123): Windows Speech dictation, press-to-talk.

Design decisions (goals.md §19i):
- The engine is the Windows Speech recognizer (winsdk). Dictation with a topic
  constraint is performed by Microsoft's Windows speech service and requires
  the Windows "Online speech recognition" toggle (Settings → Privacy &
  security → Speech). No API key, no third-party service: the chat model only
  ever receives the recognized words as text.
- `listen_once()` blocks until the student stops speaking (end silence) or a
  hard cap elapses; `cancel_active()` force-stops a running capture from
  another thread.
- Availability is probed honestly (projection present *and* the Windows
  speech toggle accepted); every Windows failure becomes a plain-language
  student message. There is no silent failure and no fabricated text.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import winreg
from typing import Callable

logger = logging.getLogger("scholarpath.voice")

MAX_LISTEN_SECONDS = 45.0

# 0x80045509 SPERR_SPEECH_PRIVACY_POLICY_NOT_ACCEPTED as a signed winerror.
_PRIVACY_DECLINED = -2147199735

try:  # pragma: no cover - the import existence varies with the SDK projection
    import winsdk.windows.media.speechrecognition as _sp
except Exception:  # noqa: BLE001 - degrade honestly, never crash at import
    _sp = None


class VoiceError(Exception):
    """Speech recognition failed with a student-facing reason message."""

    def __init__(self, student_message: str) -> None:
        super().__init__(student_message)
        self.student_message = student_message


_TOGGLE_OFF = (
    "Windows speech recognition is switched off. Open Windows Settings → "
    "Privacy & security → Speech and turn on Online speech recognition, "
    "then click the mic again."
)

_STATUS_MESSAGES = {
    "PRIVACY_DECLINED": _TOGGLE_OFF,
    "MICROPHONE_UNAVAILABLE": "No microphone is available to this app. Check "
    "Windows microphone permissions (Settings → Privacy → Microphone).",
    "AUDIO_QUALITY_FAILURE": "The microphone signal was not usable. Try a "
    "better input device or move away from noise.",
    "NETWORK_FAILURE": "Windows speech needs an internet connection for "
    "dictation. Check the connection and try again.",
    "GRAMMAR_LANGUAGE_MISMATCH": "No installed speech language matches your "
    "Windows display language. Install a supported language pack.",
    "TOPIC_LANGUAGE_NOT_SUPPORTED": "Your installed speech language cannot be "
    "used for dictation. Install an English language pack.",
    "TIMEOUT_EXCEEDED": "Nothing was heard in time. Click the mic and speak.",
    "USER_CANCELED": "Voice input was stopped.",
    "UNKNOWN": "Voice input failed. Try again.",
}


def _online_speech_enabled() -> bool:
    """Read (never write) the Windows toggle that gates dictation."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Speech_OneCore\Settings\OnlineSpeechPrivacy",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "HasAccepted")
            return bool(value)
    except OSError:
        return False


def availability() -> tuple[bool, str]:
    """(usable, reason) - an honest answer, never a silent flag."""
    if _sp is None:
        return False, (
            "Windows speech modules are not installed in this environment. "
            "Voice input stays off; typing still works."
        )
    if not _online_speech_enabled():
        return False, _TOGGLE_OFF
    try:
        _sp.SpeechRecognizer()
    except Exception as exc:  # noqa: BLE001 - any probe failure is reportable
        logger.info("voice availability probe failed: %s", exc)
        return False, "Speech recognition did not initialise on this device; voice input is off."
    return True, ""


def _student_message_for_status(status_name: str, platform_error: str) -> str:
    base = _STATUS_MESSAGES.get(status_name, _STATUS_MESSAGES["UNKNOWN"])
    return base if status_name else f"Voice input failed: {platform_error}"


async def _dictate_once(max_seconds: float = MAX_LISTEN_SECONDS) -> str:
    recognizer = _sp.SpeechRecognizer()
    language = recognizer.current_language
    constraint = _sp.SpeechRecognitionTopicConstraint(
        _sp.SpeechRecognitionScenario.DICTATION, language
    )
    recognizer.constraints.append(constraint)
    _register_active(recognizer)
    try:
        await recognizer.compile_constraints_async()
        try:
            result = await asyncio.wait_for(
                recognizer.recognize_async(), timeout=max_seconds
            )
        except asyncio.TimeoutError:
            raise VoiceError(
                f"Nothing was heard within {int(max_seconds)} seconds. "
                "Click the mic and speak."
            ) from None
        except OSError as exc:  # WinRT error surface, e.g. audio problems
            code = getattr(exc, "winerror", None)
            if code == _PRIVACY_DECLINED:
                raise VoiceError(_STATUS_MESSAGES["PRIVACY_DECLINED"]) from None
            raise VoiceError(_student_message_for_status("", str(exc))) from None
        status = str(result.status).rsplit(".", 1)[-1]
        if status != "SUCCESS":
            raise VoiceError(_student_message_for_status(status, ""))
        return result.text or ""
    finally:
        _unregister_active(recognizer)
        try:
            recognizer.close()
        except Exception:  # noqa: BLE001 - close must never mask a result
            pass


_active_lock = threading.Lock()
_active_recognizer: list[object] = []


def _register_active(recognizer: object) -> None:
    with _active_lock:
        _active_recognizer.append(recognizer)


def _unregister_active(recognizer: object) -> None:
    with _active_lock:
        if recognizer in _active_recognizer:
            _active_recognizer.remove(recognizer)


def cancel_active() -> None:
    """Force-stop any running capture (called from the UI thread)."""
    with _active_lock:
        current = list(_active_recognizer)
    for recognizer in current:
        try:
            asyncio.new_event_loop().run_until_complete(
                recognizer.stop_recognition_async()
            )
        except Exception as exc:  # noqa: BLE001 - stop failed -> time cap still holds
            logger.info("voice cancel failed (time cap still applies): %s", exc)


def listen_once(
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
    max_seconds: float = MAX_LISTEN_SECONDS,
) -> None:
    """Run one dictation capture synchronously on the calling thread.

    Designed to be called from a `QThread.run()`: the UI stays live while the
    recognizer blocks here. `cancel_active()` shortens the wait; otherwise the
    capture ends at end-silence or `max_seconds`.
    """

    async def runner() -> str:
        return await _dictate_once(max_seconds=max_seconds)

    try:
        text = asyncio.run(runner())
    except VoiceError as exc:
        on_error(exc.student_message)
        return
    except Exception:  # noqa: BLE001 - voice must never crash the app
        logger.exception("voice capture crashed")
        on_error("Voice input failed unexpectedly. Try again.")
        return
    on_done(text)

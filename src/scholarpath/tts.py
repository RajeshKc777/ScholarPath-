"""Spoken replies for live voice mode (G126, G130).

- Two engines, best first: the free Edge neural voice (`edge-tts`, no API
  key, needs the internet), then the local Windows SAPI voice through
  `pyttsx3` as an automatic offline fallback. The app never goes mute, and
  `engine_changed` says which engine actually spoke.
- Replies already passed the provider-scrub guard in the chat controller;
  this module only turns the shown text into sound.
- `clean_speech` uses `prose.speech_text`, so the voice reads sentences, not
  symbols (asterisks, dashes, backticks, headings, bullets, link syntax).
  Bare URLs become "link in the chat" instead of being read aloud.
- `to_speech` additionally truncates long replies at a sentence boundary so a
  spoken answer stays speakable; the full text stays visible in the chat.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from scholarpath.prose import speech_text

logger = logging.getLogger("scholarpath.tts")

DEFAULT_SPEECH_LIMIT = 450

# Free Edge neural voices (no API key). Aria reads warm and natural; the
# others are fallbacks in case one voice is missing on the machine.
NEURAL_VOICES = ("en-US-AriaNeural", "en-US-JennyNeural", "en-US-GuyNeural")
DEFAULT_NEURAL_VOICE = NEURAL_VOICES[0]

ENGINE_NEURAL = "neural"
ENGINE_OFFLINE = "offline"

ENGINE_LABELS = {
    ENGINE_NEURAL: "neural voice (Microsoft Edge voices, online)",
    ENGINE_OFFLINE: "offline Windows voice",
}

def clean_speech(text: str) -> str:
    """Markdown-free, URL-light version of a chat reply, fit for a voice."""
    return speech_text(text)


def to_speech(text: str, limit: int = DEFAULT_SPEECH_LIMIT) -> tuple[str, bool]:
    """(spoken text, truncated). Truncation lands on a sentence if possible."""
    spoken = clean_speech(text)
    if len(spoken) <= limit:
        return spoken, False
    window = spoken[:limit]
    sentence_end = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if sentence_end > limit // 2:
        window = window[: sentence_end + 1]
    else:
        space = window.rfind(" ")
        if space > 0:
            window = window[:space]
    window = window.rstrip()
    if window and window[-1] not in ".!?":
        window += "..."
    return window, True


def _neural_available() -> bool:
    """True when the Edge neural engine can be imported (network checked later)."""
    try:
        import edge_tts  # noqa: F401
    except Exception:  # noqa: BLE001 - any import problem means "not available"
        return False
    return True


def engine_label(engine: str) -> str:
    """Student-facing description of the voice engine in use."""
    return ENGINE_LABELS.get(engine, ENGINE_LABELS[ENGINE_OFFLINE])


class Speaker(QObject):
    """Says one utterance at a time on a worker thread; `finished` always fires.

    Two engines, in order of preference (G130):
    1. **Neural** - the free Edge neural voices (`edge-tts`, no API key). This
       is what makes the voice sound like a person instead of a robot. It
       sends the reply text to Microsoft's speech service, so it needs the
       internet.
    2. **Offline** - the local Windows voice through SAPI/pyttsx3. Used when
       the neural engine is unavailable or fails, so the app never goes mute.
    The engine actually used is reported in `engine_name` for honest UI copy.
    """

    finished = Signal()
    failed = Signal(str)
    engine_changed = Signal(str)  # which engine is really speaking

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine: object | None = None
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()
        self._engine_name = ""

    @property
    def engine_name(self) -> str:
        """Which engine spoke the last utterance ("neural" / "offline")."""
        return self._engine_name

    @staticmethod
    def available() -> tuple[bool, str]:
        if _neural_available():
            return True, ""
        try:
            import pyttsx3  # noqa: F401

            engine = pyttsx3.init()
            engine.stop()
        except Exception:  # noqa: BLE001 - honest probe, never a crash
            return False, (
                "Speech output is not available on this device. Voice mode "
                "would listen without speaking; replies stay in the chat."
            )
        return True, ""

    @property
    def speaking(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def say(self, text: str) -> None:
        """Speak `text`; `finished` fires when it ends (spoken or stopped)."""
        if not text.strip():
            self.finished.emit()
            return
        self._stopped.clear()
        thread = threading.Thread(target=self._speak, args=(text,), daemon=True)
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Best-effort interrupt of the current utterance."""
        self._stopped.set()
        engine = self._engine
        if engine is not None:
            stop = getattr(engine, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception:  # noqa: BLE001 - stop must never crash the UI
                    pass
        if self._engine_name == "neural":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:  # noqa: BLE001 - stop must never crash the UI
                pass

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the current utterance ends (tests / app shutdown)."""
        thread = self._thread
        if thread is None:
            return True
        return thread.join(timeout)

    def _speak(
        self,
        text: str,
        init: Callable[[], object] | None = None,
        engine: str | None = None,
    ) -> None:
        """Speak with the best engine available; always end with `finished`."""
        try:
            if engine in (None, ENGINE_NEURAL) and _neural_available():
                try:
                    self._engine_name = ENGINE_NEURAL
                    self.engine_changed.emit(ENGINE_NEURAL)
                    self._speak_neural(text)
                    return
                except Exception as exc:  # noqa: BLE001 - fall back, never go mute
                    logger.info("neural voice failed (%s); using the offline voice", exc)
            self._engine_name = ENGINE_OFFLINE
            self.engine_changed.emit(ENGINE_OFFLINE)
            self._speak_offline(text, init=init)
        except Exception:  # noqa: BLE001 - a silent failure would strand the loop
            self.failed.emit("The reply could not be spoken on this device.")
        finally:
            engine_obj = self._engine
            if engine_obj is not None:
                stop = getattr(engine_obj, "stop", None)
                if callable(stop):
                    try:
                        stop()
                    except Exception:  # noqa: BLE001 - close must never crash
                        pass
            self._engine = None
            self.finished.emit()

    def _speak_neural(self, text: str) -> None:
        """Synthesize with the free Edge neural voice and play it locally."""
        import asyncio
        import tempfile
        import uuid
        import winsound

        import edge_tts

        path = Path(tempfile.gettempdir()) / f"scholarpath_voice_{uuid.uuid4().hex}.mp3"
        try:

            async def synth() -> None:
                communicate = edge_tts.Communicate(text, DEFAULT_NEURAL_VOICE)
                await communicate.save(str(path))

            asyncio.run(synth())
            if not path.exists() or path.stat().st_size == 0:
                raise RuntimeError("neural voice returned no audio")
            # Playback is blocking in this worker thread, so "finished" means
            # the audio really ended; the UI can interrupt with SND_PURGE.
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def _speak_offline(self, text: str, init: Callable[[], object] | None = None) -> None:
        """Speak with the local Windows voice (no network)."""
        import pyttsx3

        engine = init() if init is not None else pyttsx3.init()
        self._engine = engine
        engine.say(text)
        engine.runAndWait()

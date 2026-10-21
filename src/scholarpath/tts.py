"""Spoken replies for live voice mode (G126).

- The engine is Windows SAPI through `pyttsx3`: fully offline, no API key,
  no cloud service, no audio ever leaves the device. Replies already passed
  the provider-scrub guard in the chat controller; this module only turns the
  shown text into sound.
- `clean_speech` strips markdown so the voice reads sentences, not symbols
  (asterisks, backticks, headings, bullets, link syntax). Bare URLs become
  "link in the chat" instead of being read aloud.
- `to_speech` additionally truncates long replies at a sentence boundary so a
  spoken answer stays speakable; the full text stays visible in the chat.
"""

from __future__ import annotations

import re
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal

DEFAULT_SPEECH_LIMIT = 450

_URL_RE = re.compile(r"https?://\S+")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MD_EMPH_RE = re.compile(r"\*\*?([^*]+)\*\*?|__([^_]+)__")
_CODE_RE = re.compile(r"`([^`]*)`")
_HEADING_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+", re.MULTILINE)


def clean_speech(text: str) -> str:
    """Markdown-free, URL-light version of a chat reply, fit for a voice."""
    spoken = _MD_LINK_RE.sub(r"\1", text)
    spoken = _URL_RE.sub("link in the chat", spoken)
    spoken = _CODE_RE.sub(r"\1", spoken)

    def _emphasis(match: re.Match[str]) -> str:
        return match.group(1) or match.group(2) or ""

    spoken = _MD_EMPH_RE.sub(_emphasis, spoken)
    spoken = _HEADING_RE.sub("", spoken)
    spoken = _BULLET_RE.sub("", spoken)
    spoken = re.sub(r"\s+", " ", spoken)
    return spoken.strip()


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


class Speaker(QObject):
    """Says one utterance at a time on a worker thread; `finished` always fires."""

    finished = Signal()
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine: object | None = None
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()

    @staticmethod
    def available() -> tuple[bool, str]:
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

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the current utterance ends (tests / app shutdown)."""
        thread = self._thread
        if thread is None:
            return True
        return thread.join(timeout)

    def _speak(self, text: str, init: Callable[[], object] | None = None) -> None:
        try:
            import pyttsx3

            engine = init() if init is not None else pyttsx3.init()
            self._engine = engine
            engine.say(text)
            engine.runAndWait()
        except Exception:  # noqa: BLE001 - a silent failure would strand the loop
            self.failed.emit("The reply could not be spoken on this device.")
        finally:
            engine = self._engine
            if engine is not None:
                stop = getattr(engine, "stop", None)
                if callable(stop):
                    try:
                        stop()
                    except Exception:  # noqa: BLE001 - close must never crash
                        pass
            self._engine = None
            self.finished.emit()

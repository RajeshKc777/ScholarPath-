"""One real-mic Live voice cycle, with echo measurement (G174).

This is the only part of the voice work that uses the real microphone and the
real speech services. The app's log never receives the words; this console
does, because the probe exists to show them to you. Nothing is written to
disk: every clip lives in memory and is thrown away when the probe ends.

What it measures, in order:

1. **Your input** - the normal Live voice input through the app's own
   ``listen_once`` (the VAD decides when you stopped). It prints the heard
   text, the clip length, how the wait ended and the confidence.
2. **The room** - two seconds of raw audio with nothing playing: the noise
   floor (peak and RMS amplitude).
3. **The reply playing** - raw audio for the whole reply, with no endpointing
   at all. It prints the levels (so you can see whether the microphone hears
   the speaker at all) and the transcript, which is the echo check: if the
   transcript contains the reply, the loop must never open the microphone
   while a reply plays.
4. **Right after the reply** - the same raw recording for a few seconds once
   the audio has stopped. It prints the levels and the transcript, which is
   the room-tail check.
5. **What the app would get** - the app's own ``listen_once`` the moment the
   reply ends, exactly like the Live loop does today.

Nothing is fixed here, and nothing is stored.

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\voice_probe.py

Useful flags: ``--language en-GB``, ``--skip-student`` (no human needed for
the echo windows), ``--no-speak`` (microphone only), ``--reply "..."``.
"""

from __future__ import annotations

import argparse
import array
import logging
import re
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from scholarpath import tts, voice  # noqa: E402

DEFAULT_STUDENT = "Find scholarships in Germany."
DEFAULT_REPLY = (
    "I found three scholarships in Germany. The first one closes on the "
    "thirty-first of January."
)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def _overlap(reply: str, heard: str) -> tuple[int, int]:
    """(reply words the transcript contains, reply words in total)."""
    reply_words = _words(reply)
    if not reply_words:
        return 0, 0
    return len(reply_words & _words(heard)), len(reply_words)


# -- raw recording (no endpointing) ------------------------------------------


def _levels(raw: bytes, sample_width: int = 2) -> tuple[int, int]:
    """(peak, rms) of a 16-bit mono clip, both scaled to 0-32767."""
    if sample_width != 2 or not raw:
        return 0, 0
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    if not samples:
        return 0, 0
    peak = max(max(samples), -min(samples))
    total = sum(int(sample) * int(sample) for sample in samples)
    rms = int((total / len(samples)) ** 0.5)
    return abs(peak), rms


def _record_raw(seconds: float, delay: float = 0.0):
    """Record `seconds` of raw audio with no endpointing at all."""
    import speech_recognition as sr

    with sr.Microphone() as source:
        if delay:
            time.sleep(delay)
        frames = source.stream.read(int(source.SAMPLE_RATE * seconds))
        audio = sr.AudioData(frames, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
    return audio


def _transcribe(audio, language: str) -> tuple[str, float | None]:
    """Transcribe a raw clip; the words stay in this console."""
    import speech_recognition as sr

    recognizer = sr.Recognizer()
    try:
        return voice._transcribe_google(recognizer, audio, language)
    except voice.VoiceError as exc:
        print(f"  transcript: (nothing intelligible) - {exc.student_message}")
        return "", None


# -- the app's own capture ----------------------------------------------------


def _capture(
    *,
    phrase_seconds: float,
    start_timeout: float,
    language: str,
    is_speaking=None,
) -> dict:
    """One listen_once() call, with its numbers kept for the report."""
    result: dict = {"text": "", "error": "", "stats": None}
    started = time.monotonic()

    def done(text: str) -> None:
        result["text"] = text

    def failed(message: str) -> None:
        result["error"] = message

    def stats(value: voice.CaptureStats) -> None:
        result["stats"] = value

    voice.listen_once(
        done,
        failed,
        max_seconds=phrase_seconds,
        language=language,
        start_timeout=start_timeout,
        is_speaking=is_speaking,
        on_stats=stats,
    )
    result["started_at"] = started
    result["ended_at"] = time.monotonic()
    return result


def _show(label: str, result: dict) -> None:
    stats = result["stats"]
    print(f"\n[{label}]")
    if result["text"]:
        print(f"  heard      : {result['text']!r}")
    else:
        print(f"  heard      : (nothing)  {result['error']}")
    if stats is not None:
        confidence = "not sent" if stats.confidence is None else f"{stats.confidence:.2f}"
        print(
            f"  duration   : wait {stats.duration_s:.2f}s, clip {stats.audio_s:.2f}s\n"
            f"  ended      : {stats.reason}   tts_playing: {stats.tts_playing}\n"
            f"  engine     : {stats.engine} ({stats.language})   "
            f"confidence: {confidence}   chars: {stats.chars}"
        )
    print(f"  wall time  : {result['ended_at'] - result['started_at']:.2f}s")


def _echo_line(reply: str, heard: str) -> str:
    hits, total = _overlap(reply, heard)
    share = (hits / total * 100.0) if total else 0.0
    verdict = "ECHO" if hits >= max(2, total // 4) else "no reply words heard"
    return f"{hits}/{total} reply words ({share:.0f}%) - {verdict}"


def _level_line(label: str, peak: int, rms: int) -> None:
    print(f"  {label:16s}: peak {peak:5d}, rms {rms:5d}  (of 32767)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ScholarPath Live voice probe")
    parser.add_argument("--language", default="en-IN", help="speech-service language tag")
    parser.add_argument("--student", default=DEFAULT_STUDENT, help="sentence to say for the input test")
    parser.add_argument("--reply", default=DEFAULT_REPLY, help="canned reply to speak for the echo test")
    parser.add_argument("--skip-student", action="store_true", help="skip the human utterance")
    parser.add_argument("--no-speak", action="store_true", help="skip the two echo windows")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    _app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841

    usable, reason = voice.availability()
    speakable, speak_reason = tts.Speaker.available()

    print("ScholarPath Live voice probe (G174) - nothing is stored")
    print(f"microphone : {'yes' if usable else 'no - ' + reason}")
    print(f"speaker    : {'yes' if speakable else 'no - ' + speak_reason}")
    if not usable:
        return 2

    if not args.skip_student:
        print(f'\nSay this now (the microphone is about to open): "{args.student}"')
        student = _capture(
            phrase_seconds=20.0,
            start_timeout=20.0,
            language=args.language,
        )
        _show("you, live input", student)
        if student["text"]:
            hits, total = _overlap(args.student, student["text"])
            print(f"  vs expected: {hits}/{total} words matched")

    # -- the room ------------------------------------------------------------
    ambient = _record_raw(2.0)
    peak, rms = _levels(ambient.frame_data, ambient.sample_width)
    print("\n[the room, nothing playing]")
    _level_line("2s of silence", peak, rms)

    if args.no_speak or not speakable:
        if not speakable:
            print("\nNo speaker engine - the echo windows cannot run.")
        return 0

    speaker = tts.Speaker()

    # -- the reply, recorded raw while it plays ------------------------------
    print("\nSpeak the reply now; the microphone records it raw...")
    talker = {}

    def speak() -> None:
        speaker.say(args.reply)
        speaker.wait(120.0)

    thread = threading.Thread(target=speak, daemon=True)
    thread.start()
    time.sleep(0.4)  # the mic is already open before the first sound
    playing = _record_raw(14.0)
    thread.join(120.0)
    peak, rms = _levels(playing.frame_data, playing.sample_width)
    print("\n[the reply playing, raw]")
    _level_line("while it played", peak, rms)
    heard, _confidence = _transcribe(playing, args.language)
    if heard:
        print(f"  transcript: {heard!r}")
    print(f"  echo: {_echo_line(args.reply, heard)}")

    # -- the room right after the reply ---------------------------------------
    tail = _record_raw(3.0)
    peak, rms = _levels(tail.frame_data, tail.sample_width)
    print("\n[the three seconds after the reply, raw]")
    _level_line("after the sound", peak, rms)
    heard, _confidence = _transcribe(tail, args.language)
    if heard:
        print(f"  transcript: {heard!r}")
    print(f"  echo: {_echo_line(args.reply, heard)}")

    # -- what the app would get, the moment the reply ends -------------------
    print("\nSpeak the reply again, then this probe listens at once (the current loop)...")
    speaker.say(args.reply)
    speaker.wait(120.0)
    play_ended = time.monotonic()
    after = _capture(
        phrase_seconds=15.0,
        start_timeout=12.0,
        language=args.language,
        is_speaking=lambda: speaker.speaking,
    )
    _show("right after playback", after)
    print(f"  listen started {after['started_at'] - play_ended:.3f}s after the reply ended")
    print(f"  echo: {_echo_line(args.reply, after['text'])}")

    print(
        "\nWhat to look for: ECHO in the playback window means the loop must "
        "never open the microphone while a reply plays. ECHO just after means "
        "the old sound was still in the room, so a short pause is needed. A "
        "clip that ends after a second or two, while the reply is still "
        "playing, points at endpointing. Unrelated words point at engine "
        "accuracy or noise."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

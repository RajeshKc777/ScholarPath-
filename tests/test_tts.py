"""Spoken replies: markdown cleaning, truncation, speaker lifecycle (G126)."""

from __future__ import annotations

from scholarpath.tts import (
    DEFAULT_SPEECH_LIMIT,
    Speaker,
    clean_speech,
    to_speech,
)


def test_clean_speech_strips_markdown_symbols() -> None:
    raw = "## Head\n- **point one**\n- `code` and *italic* text"
    spoken = clean_speech(raw)
    assert "**" not in spoken and "`" not in spoken and "#" not in spoken
    assert "Head point one code and italic text" in spoken


def test_clean_speech_replaces_bare_urls() -> None:
    spoken = clean_speech("See https://example.com/very/long/link for details")
    assert "https://" not in spoken
    assert "link in the chat" in spoken


def test_clean_speech_keeps_link_labels_drops_targets() -> None:
    spoken = clean_speech("check the [Chevening page](https://chevening.org)")
    assert "Chevening page" in spoken
    assert "chevening.org" not in spoken


def test_clean_speech_collapses_whitespace() -> None:
    spoken = clean_speech("line one\n\nline two   spaced\ttab")
    assert spoken == "line one line two spaced tab"


def test_to_speech_short_reply_is_untouched() -> None:
    speech, truncated = to_speech("Yes, you are eligible for the grant.")
    assert speech == "Yes, you are eligible for the grant."
    assert not truncated


def test_to_speech_truncates_at_a_sentence() -> None:
    long = ". ".join(f"Sentence number {i}" for i in range(60)) + "."
    speech, truncated = to_speech(long, limit=120)
    assert truncated
    assert len(speech) <= 130  # sentence boundary keeps it near the limit
    assert speech.endswith(("!", ".", "..."))


def test_to_speech_truncates_at_a_word_when_no_sentence() -> None:
    speech, truncated = to_speech("word " * 200, limit=40)
    assert truncated
    assert not speech.endswith("wordword")


def test_default_limit_is_speakable() -> None:
    assert 200 <= DEFAULT_SPEECH_LIMIT <= 900


def test_speaker_availability_is_honest() -> None:
    usable, reason = Speaker.available()
    assert isinstance(usable, bool)
    if not usable:
        assert "replies stay in the chat" in reason


def test_speak_runs_uses_a_passed_engine_and_always_finishes() -> None:
    calls: list[str] = []

    class FakeEngine:
        def say(self, text: str) -> None:
            calls.append(f"say:{text}")

        def runAndWait(self) -> None:  # noqa: N802 - third-party API
            calls.append("run")

        def stop(self) -> None:  # noqa: N802 - third-party API
            calls.append("stop")

    speaker = Speaker()
    done: list[bool] = []
    speaker.finished.connect(lambda: done.append(True))
    speaker._speak("hello there", init=lambda: FakeEngine())
    assert calls == ["say:hello there", "run", "stop"]
    assert done == [True]


def test_speak_failure_reports_and_still_finishes() -> None:
    def boom() -> object:
        raise RuntimeError("no engine")

    speaker = Speaker()
    failures: list[str] = []
    speaker.failed.connect(failures.append)
    speaker._speak("text", init=boom)
    assert failures and "could not be spoken" in failures[0]

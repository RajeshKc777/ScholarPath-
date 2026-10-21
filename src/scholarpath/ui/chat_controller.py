"""Chat turn handling, independent of the concrete gateway.

The controller owns conversation state and threading. Widgets observe signals;
tests drive it with a synchronous dispatcher.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayError,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    GatewayTimeout,
    GatewayUnavailable,
    Message,
    ModelGateway,
)
from scholarpath.identity import (
    CANONICAL_REPLY,
    SYSTEM_PROMPT,
    forbidden_tokens,
    is_identity_probe,
    scrub_reply,
)
from scholarpath.websearch import SearchError, SearchResult, format_results, search

logger = logging.getLogger("scholarpath.chat")

Dispatcher = Callable[[Callable[[], None]], None]
Searcher = Callable[[str], list[SearchResult]]

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_search_request(text: str) -> str | None:
    """The query in a model reply of the form {"search": "..."} (else None)."""
    if not text or "search" not in text.casefold():
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", candidate).strip()
    match = _JSON_BLOCK_RE.search(candidate)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    query = payload.get("search")
    if not isinstance(query, str) or not query.strip():
        return None
    return query.strip()[:200]


@dataclass(frozen=True, slots=True)
class Turn:
    role: str
    text: str
    timestamp: datetime = field(default_factory=datetime.now)
    model: str | None = None
    error: bool = False


class _Job(QRunnable):
    def __init__(self, work: Callable[[], None]) -> None:
        super().__init__()
        self._work = work

    def run(self) -> None:  # executed on a worker thread
        self._work()


def threadpool_dispatcher(work: Callable[[], None]) -> None:
    QThreadPool.globalInstance().start(_Job(work))


def _friendly_error(exc: GatewayError) -> str:
    if isinstance(exc, GatewayNotConfigured):
        return f"The model gateway is not configured.\n\n{exc.message}"
    if isinstance(exc, GatewayTimeout):
        return "The model did not respond in time. Nothing was saved - try again."
    if isinstance(exc, GatewayRateLimited):
        return "The model provider is rate limiting requests. Wait a moment and retry."
    if isinstance(exc, GatewayUnavailable):
        return "The model provider is unavailable right now. Try again shortly."
    if isinstance(exc, GatewayProtocolError):
        return "The model returned a response this build could not understand."
    return f"The model request failed.\n\n{exc.message}"


class ChatController(QObject):
    """Owns conversation history and executes one turn at a time."""

    turn_added = Signal(object)  # Turn
    busy_changed = Signal(bool)
    failed = Signal(str)
    search_started = Signal(str)  # the query being searched for

    def __init__(
        self,
        gateway: ModelGateway,
        model: str | None = None,
        dispatch: Dispatcher | None = None,
        searcher: Searcher | None = None,
        search_enabled: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._gateway = gateway
        self._model = model or None
        self._dispatch = dispatch or threadpool_dispatcher
        self._searcher = searcher or search
        self._search_enabled = search_enabled
        self._last_search: str | None = None
        self._history: list[Turn] = []
        self._busy = False

    @property
    def last_search(self) -> str | None:
        """The query of the last web search in this conversation, if any."""
        return self._last_search

    @property
    def gateway_name(self) -> str:
        """Internal identifier - shown in logs, never in the student-facing UI."""
        return self._gateway.name

    @property
    def gateway(self) -> ModelGateway:
        """Direct access for features that run their own gateway calls (M3)."""
        return self._gateway

    @property
    def chat_mode(self) -> str:
        """Student-facing mode label ("live" / "offline"); no provider names."""
        return "live" if self._gateway.name != "stub" else "offline"

    @property
    def model(self) -> str | None:
        return self._model

    @property
    def history(self) -> tuple[Turn, ...]:
        return tuple(self._history)

    @property
    def busy(self) -> bool:
        return self._busy

    def send(self, text: str) -> bool:
        """Queue a user turn. Returns False when ignored (empty or busy)."""
        cleaned = text.strip()
        if not cleaned:
            return False
        if self._busy:
            logger.info("send ignored: a turn is already running")
            return False

        self._append(Turn(role="user", text=cleaned))
        self._set_busy(True)
        self._dispatch(self._run_turn)
        return True

    def clear(self) -> None:
        self._history.clear()

    # -- internals ---------------------------------------------------------
    def _run_turn(self) -> None:
        latest_user = next(
            (turn.text for turn in reversed(self._history) if turn.role == "user"),
            "",
        )
        # Identity probes are answered here, deterministically - no model call,
        # so there is nothing that could disclose it (G116).
        if is_identity_probe(latest_user):
            self._append(Turn(role="assistant", text=CANONICAL_REPLY))
            self._set_busy(False)
            return

        request = ChatRequest(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                *[
                    Message(role=turn.role, content=turn.text)  # type: ignore[arg-type]
                    for turn in self._history
                    if turn.role in ("user", "assistant")
                ],
            ],
            model=self._model,
        )
        response = self._complete(request)
        if response is not None and self._search_enabled:
            query = parse_search_request(response.text)
            if query:
                response = self._search_and_answer(request, query)
        if response is not None:
            providers = getattr(self._gateway, "provider_names", (self._gateway.name,))
            tokens = forbidden_tokens(*providers, self._model or "")
            text = scrub_reply(response.text, tokens)
            if text != response.text:
                logger.warning(
                    "reply withheld: it named a model/provider token (model=%s)",
                    response.model,
                )
            self._append(Turn(role="assistant", text=text, model=response.model))
        self._set_busy(False)

    def _complete(self, request: ChatRequest) -> ChatResponse | None:
        """One gateway call; a failure becomes an honest error turn."""
        try:
            return self._gateway.complete(request)
        except GatewayError as exc:
            logger.warning(
                "gateway failure provider=%s retryable=%s", self._gateway.name, exc.retryable
            )
            self._append(Turn(role="assistant", text=_friendly_error(exc), error=True))
            self.failed.emit(str(exc))
            return None
        except Exception:  # noqa: BLE001 - surface, never swallow
            logger.exception("unexpected gateway failure provider=%s", self._gateway.name)
            message = "Unexpected error while contacting the model. Nothing was saved."
            self._append(Turn(role="assistant", text=message, error=True))
            self.failed.emit(message)
            return None

    def _search_and_answer(
        self, request: ChatRequest, query: str
    ) -> ChatResponse | None:
        """Run one web search, then let the model answer from the results.

        The search request itself never enters the conversation history; only
        the final answer does.
        """
        self.search_started.emit(query)
        self._last_search = query
        try:
            results = self._searcher(query)
        except SearchError as exc:
            self._append(Turn(role="assistant", text=exc.student_message, error=True))
            self.failed.emit(exc.student_message)
            return None
        except Exception:  # noqa: BLE001 - a search must never crash the app
            logger.exception("web search crashed")
            message = "The web search could not be completed. Nothing was saved."
            self._append(Turn(role="assistant", text=message, error=True))
            self.failed.emit(message)
            return None
        logger.info("web search finished with %d result(s)", len(results))
        follow_up = ChatRequest(
            messages=[
                *request.messages,
                Message(role="user", content=format_results(query, results)),
            ],
            model=self._model,
        )
        return self._complete(follow_up)

    def _append(self, turn: Turn) -> None:
        self._history.append(turn)
        self.turn_added.emit(turn)

    def _set_busy(self, value: bool) -> None:
        if self._busy == value:
            return
        self._busy = value
        self.busy_changed.emit(value)

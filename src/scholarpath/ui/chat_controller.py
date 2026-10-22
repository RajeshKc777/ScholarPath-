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

from scholarpath.chat_context import catalog_message, level_note, profile_summary
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
from scholarpath.search import SearchHit
from scholarpath.websearch import SearchError, SearchResult, format_results, search

logger = logging.getLogger("scholarpath.chat")

Dispatcher = Callable[[Callable[[], None]], None]
Searcher = Callable[[str], list[SearchResult]]
ProfileProvider = Callable[[], dict | None]
CatalogProvider = Callable[[str], list[SearchHit]]

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

SEARCH_OFF_NOTE = (
    "Web search is switched off in this build, so you cannot look anything up. "
    "Answer from what you know, and say plainly that you could not check live "
    "pages or current deadlines. Never claim to have searched."
)
SEARCH_OFF_ANSWER = (
    "Web search is switched off in this build, so the pages for "
    '"search" could not be fetched. Answer the student from what you know, '
    "state clearly that you could not check live pages or current deadlines, "
    "and never claim to have searched. Plain prose, no markdown."
)

SEARCH_REQUEST_RETRY = (
    "The app can run the web search for you - never say that you cannot "
    "search, browse or reach the internet. If the student's last message "
    'needs live results, reply with exactly {"search": "<short query>"} and '
    "nothing else, and the app will send you the results. If it needs no "
    "live results, answer it normally."
)

#: Words that mark a refusal, and words that mark the web. A reply that has
#: both is the model saying it cannot look anything up (G179).
_REFUSAL_WORDS = (
    "can't",
    "cannot",
    "can not",
    "unable to",
    "not able to",
    "don't have",
    "do not have",
    "no access",
    "not available",
    "isn't available",
    "is not available",
)

_WEB_WORDS = (
    "web",
    "internet",
    "online",
    "website",
    "webpage",
    "browser",
    "live page",
    "live information",
)


def is_search_refusal(text: str) -> bool:
    """True when a reply says it cannot look anything up on the web."""
    lowered = " ".join((text or "").casefold().split())
    if not lowered:
        return False
    if not any(word in lowered for word in _WEB_WORDS):
        return False
    return any(word in lowered for word in _REFUSAL_WORDS)


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
        profile: ProfileProvider | None = None,
        catalog: CatalogProvider | None = None,
        context_enabled: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._gateway = gateway
        self._model = model or None
        self._dispatch = dispatch or threadpool_dispatcher
        self._searcher = searcher or search
        self._search_enabled = search_enabled
        self._profile = profile
        self._catalog = catalog
        self._context_enabled = bool(context_enabled)
        self._last_search: str | None = None
        self._history: list[Turn] = []
        self._busy = False

    @property
    def last_search(self) -> str | None:
        """The query of the last web search in this conversation, if any."""
        return self._last_search

    @property
    def search_enabled(self) -> bool:
        """Whether the next model turn may search the web."""
        return self._search_enabled

    @search_enabled.setter
    def search_enabled(self, enabled: bool) -> None:
        self._search_enabled = bool(enabled)
        logger.info("web search %s", "enabled" if self._search_enabled else "disabled")

    @property
    def context_enabled(self) -> bool:
        """Whether the chat may be given the saved profile's summary."""
        return self._context_enabled

    @context_enabled.setter
    def context_enabled(self, enabled: bool) -> None:
        self._context_enabled = bool(enabled)
        logger.info(
            "profile context %s", "on" if self._context_enabled else "off"
        )

    @property
    def profile_provider(self) -> ProfileProvider | None:
        """Where the saved profile comes from (set by the window)."""
        return self._profile

    @profile_provider.setter
    def profile_provider(self, provider: ProfileProvider | None) -> None:
        self._profile = provider

    @property
    def catalog_provider(self) -> CatalogProvider | None:
        """Where the verified catalog comes from (set by the window)."""
        return self._catalog

    @catalog_provider.setter
    def catalog_provider(self, provider: CatalogProvider | None) -> None:
        self._catalog = provider

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
    def _context_messages(self, question: str) -> list[Message]:
        """The profile summary, the level rule and the verified catalog."""
        if not self._context_enabled:
            return []
        messages: list[Message] = []
        profile: dict | None = None
        if self._profile is not None:
            try:
                profile = self._profile()
            except Exception:  # noqa: BLE001 - a profile problem must not break chat
                logger.exception("the profile could not be read for the chat")
                profile = None
            summary = profile_summary(profile)
            if summary:
                messages.append(Message(role="system", content=summary))
            note = level_note(profile)
            if note:
                messages.append(Message(role="system", content=note))
        if self._catalog is not None:
            try:
                hits = self._catalog(question) or []
            except Exception:  # noqa: BLE001 - a catalog problem must not break chat
                logger.exception("the catalog could not be searched for the chat")
                hits = []
            block = catalog_message(hits, profile)
            if block:
                messages.append(Message(role="system", content=block))
        return messages

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
                *self._context_messages(latest_user),
                *(
                    [Message(role="system", content=SEARCH_OFF_NOTE)]
                    if not self._search_enabled
                    else []
                ),
                *[
                    Message(role=turn.role, content=turn.text)  # type: ignore[arg-type]
                    for turn in self._history
                    if turn.role in ("user", "assistant")
                ],
            ],
            model=self._model,
        )
        response = self._complete(request)
        if response is not None:
            query = parse_search_request(response.text)
            if query is None and self._search_enabled and is_search_refusal(response.text):
                # The model said it cannot search while the app can: ask it
                # once more in the exact form the app understands (G179).
                response = self._ask_for_search_again(request)
                query = parse_search_request(response.text) if response is not None else None
            if query and self._search_enabled:
                response = self._search_and_answer(request, query)
            elif query:
                # The student has not allowed web search: the model must say
                # so rather than pretend it looked (privacy.web_search).
                response = self._answer_without_search(request, query)
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

    def _answer_without_search(
        self, request: ChatRequest, query: str
    ) -> ChatResponse | None:
        """Search is switched off: the model is told, and answers honestly."""
        logger.info("web search was requested but is switched off")
        follow_up = ChatRequest(
            messages=[
                *request.messages,
                Message(role="user", content=SEARCH_OFF_ANSWER),
            ],
            model=self._model,
        )
        return self._complete(follow_up)

    def _ask_for_search_again(self, request: ChatRequest) -> ChatResponse | None:
        """One retry when the model refused to ask for a search (G179).

        The app can search, so a "I cannot browse the web" reply is the
        model refusing, not a limit of the app. The retry asks for the
        search request in the exact form the app reads. One retry only.
        """
        logger.info("the model refused to ask for a search; asking once more")
        follow_up = ChatRequest(
            messages=[
                *request.messages,
                Message(role="user", content=SEARCH_REQUEST_RETRY),
            ],
            model=self._model,
        )
        return self._complete(follow_up)

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

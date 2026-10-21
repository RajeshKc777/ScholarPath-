"""HTTP adapter for the local OpenCode server (Milestone 2).

Verified against OpenCode 2.0.29:

- Service discovery: the background service registers ``service.json`` with its
  URL, PID and a private password (standard path:
  ``~/.local/state/opencode/service.json``).
- Authentication: ``Authorization: Basic base64("opencode:<password>")``.
- A completion is one short-lived session: create session -> prompt -> wait for
  idle -> read the assistant message -> delete the session.
- ``POST /api/experimental/generate`` exists but the provider rejects it for the
  free tier ("can only be used from within OpenCode"); the session path works and
  is what the official client uses.

Nothing here invents a reply. Every failure becomes a typed ``GatewayError`` with
a message the UI can show.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scholarpath.config import GatewayConfig
from scholarpath.gateway.base import (
    ChatRequest,
    ChatResponse,
    GatewayError,
    GatewayNotConfigured,
    GatewayProtocolError,
    GatewayRateLimited,
    GatewayTimeout,
    GatewayUnavailable,
)
from scholarpath.gateway.credentials import CredentialStore, configured_account_keys
from scholarpath.gateway.failover import ModelChain, free_tier_alternatives
from scholarpath.gateway.registry import ModelRef, ModelRegistry, parse_model_ref

logger = logging.getLogger("scholarpath.gateway.opencode")

AUTH_USER = "opencode"
PASSWORD_ENV = "OPENCODE_SERVICE_PASSWORD"
DEFAULT_TITLE = "ScholarPath chat"

# How many accounts one model may be tried on before the chain moves on.
ACCOUNT_ROTATIONS_PER_MODEL = 1

# How long a model stays skipped after this account hit its quota.
EXHAUSTED_COOLDOWN_SECONDS = 300.0

# How many accounts a model may fail on before it is treated as out of quota
# for this setup as a whole.
MODEL_FAILURE_LIMIT = 2

SYSTEM_PROMPT = (
    "You are ScholarPath AI, a scholarship assistant for students.\n"
    "Rules you must follow:\n"
    "- Never invent scholarships, deadlines, funding amounts, URLs or eligibility criteria.\n"
    "- If you do not know or cannot verify something, say so plainly.\n"
    "- This build can read official pages the user supplies, and the app can run a\n"
    "  web search on request. Do not claim to have researched anything you were\n"
    "  not given: if the student needs live results, reply with exactly\n"
    '  {"search": "<short query>"} and nothing else - the app will search and\n'
    "  send you the results. Then answer only from those results, naming the\n"
    "  pages you used with their URLs, and say so plainly when they do not\n"
    "  answer the question.\n"
    "- Keep answers short and useful. Ask for missing facts instead of guessing.\n"
    "- Write like a person talking to a student, not like a document: plain sentences,\n"
    "  contractions, short paragraphs. No markdown at all - no asterisks, no bold,\n"
    "  no dash bullets, no headings, no tables, no emoji. If several things need\n"
    "  saying, use short sentences instead of a list. No filler openings."
)


@dataclass(frozen=True, slots=True)
class ServiceEndpoint:
    """A discovered OpenCode background service."""

    url: str
    password: str
    source: str = ""


def service_file_candidates(explicit: str | None = None) -> list[Path]:
    """Registration file locations, most explicit first."""
    paths: list[Path] = []
    if explicit:
        paths.append(Path(explicit).expanduser())

    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        paths.append(Path(xdg_state) / "opencode" / "service.json")
    paths.append(Path.home() / ".local" / "state" / "opencode" / "service.json")

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        paths.append(Path(local_app_data) / "opencode" / "service.json")
    paths.append(Path.home() / ".config" / "opencode" / "service.json")

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def discover_service(explicit: str | None = None) -> ServiceEndpoint:
    """Read the registered service endpoint. Raises GatewayNotConfigured.

    With an explicit file, that file is the only candidate - tests must be able
    to run without a global OpenCode installation leaking in.
    """
    if explicit:
        candidates = [Path(explicit).expanduser()]
    else:
        candidates = service_file_candidates(None)

    checked: list[str] = []
    for path in candidates:
        checked.append(str(path))
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("cannot read OpenCode service file %s: %s", path, exc)
            continue
        url = str(payload.get("url") or "").strip()
        password = str(payload.get("password") or "").strip()
        if not url or not password:
            continue
        return ServiceEndpoint(url=url.rstrip("/"), password=password, source=str(path))

    raise GatewayNotConfigured(
        "No running OpenCode service was found.\n\n"
        "Start it with `opencode serve` (or open the OpenCode app), then retry.\n"
        "Checked:\n  " + "\n  ".join(checked)
    )


def _error_message(body: str) -> str:
    cleaned = body.strip()
    if not cleaned:
        return "no response body"
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned[:300]
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("_tag")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return cleaned[:300]


def _is_quota_error(detail: Any) -> bool:
    """True when the provider refused because a quota or rate limit was hit."""
    if not isinstance(detail, dict):
        return False
    kind = str(detail.get("type") or "").casefold()
    message = str(detail.get("message") or "").casefold()
    if "quota" in kind or "rate" in kind:
        return True
    return any(
        token in message
        for token in ("rate limit", "rate-limit", "too many requests", "quota", "insufficient")
    )


class _EmptyReply(GatewayProtocolError):
    """The model answered with nothing usable - another model may do better."""

    retryable = True


class OpenCodeGateway:
    """ModelGateway backed by the local OpenCode HTTP server."""

    name = "opencode"

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config
        self._timeout = float(config.timeout_seconds)

        if config.base_url.strip():
            base_url = config.base_url.strip().rstrip("/")
            password = os.environ.get(PASSWORD_ENV, "").strip()
            if not password:
                raise GatewayNotConfigured(
                    "gateway.base_url is set, so the server password must come from "
                    f"the {PASSWORD_ENV} environment variable. It is never stored in "
                    "config.toml or in source control."
                )
            self._base_url = base_url
            self._endpoint_source = "config.base_url"
        else:
            endpoint = discover_service(config.service_file.strip() or None)
            self._base_url = endpoint.url
            self._endpoint_source = endpoint.source
            password = endpoint.password

        parsed = urlparse(self._base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise GatewayNotConfigured(
                f"Invalid OpenCode server URL: {self._base_url!r}. "
                "Expected something like http://127.0.0.1:4096."
            )

        self._auth = "Basic " + base64.b64encode(
            f"{AUTH_USER}:{password}".encode("utf-8")
        ).decode("ascii")
        self._location = (config.location_dir or str(Path.cwd())).strip()
        self._registry: ModelRegistry | None = None
        self._catalog_error: GatewayError | None = None
        self._chain = ModelChain.from_ids(config.models)
        self._max_attempts = int(config.failover_attempts)
        self._rotator: CredentialStore | None = None
        self._tried_credentials: set[str] = set()
        self._active_account: str = ""
        self._exhausted: dict[tuple[str, str], float] = {}
        self._model_failures: dict[str, tuple[int, float]] = {}
        self._keys_registered = False
        logger.info("opencode gateway ready at %s (%s)", self._base_url, self._endpoint_source)

    # -- public ------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def registry(self) -> ModelRegistry:
        """Model catalogue, loaded lazily and cached."""
        if self._registry is None:
            self._registry = self._load_registry()
        return self._registry

    def complete(self, request: ChatRequest) -> ChatResponse:
        """One completion, with failover over models and accounts.

        A rate-limited model is not the end of the turn: the service is asked
        to switch account first, and when that does not help the next model in
        the chain is tried. Only when every option is exhausted does the caller
        get an honest error.
        """
        prompt = self._compose_prompt(request)
        plan = self._model_plan(request)
        self._register_configured_keys()

        attempts = 0
        last_error: GatewayError | None = None
        for ref in plan:
            # One account per attempt, at most two accounts per model, so a
            # single stubborn model cannot use up the whole budget.
            for _ in range(ACCOUNT_ROTATIONS_PER_MODEL + 1):
                if attempts >= self._max_attempts:
                    break
                attempts += 1
                try:
                    return self._complete_with(ref, prompt)
                except GatewayRateLimited as exc:
                    last_error = exc
                    logger.info("model %s is rate limited (%s)", ref, exc.message)
                    self._mark_exhausted(ref)
                    if not self._rotate_credential():
                        break  # no account left - next model
                except GatewayError as exc:
                    if not exc.retryable:
                        raise
                    last_error = exc
                    break  # next model
            if attempts >= self._max_attempts:
                break

        if isinstance(last_error, GatewayRateLimited):
            raise GatewayRateLimited(
                "The model service is rate limited on every model and account tried "
                f"({attempts} attempts). Wait a few minutes and try again."
            ) from last_error
        if isinstance(last_error, GatewayError):
            raise last_error
        raise GatewayUnavailable("No model answered the request.")

    def _complete_with(self, ref: ModelRef, prompt: str) -> ChatResponse:
        session_id: str | None = None
        try:
            session_id = self._create_session(ref)
            prompted_at = self._send_prompt(session_id, prompt)
            self._wait_for_idle(session_id)
            message = self._await_assistant_reply(session_id, prompted_at)
            return self._to_response(message, ref)
        finally:
            if session_id:
                self._delete_session(session_id)

    # -- failover ----------------------------------------------------------
    def _model_plan(self, request: ChatRequest) -> tuple[ModelRef, ...]:
        """The models to try, in order.

        Primary model first (request override, then configuration, then the
        first configured chain entry), then the configured chain, then the
        provider's free-tier alternatives. Paid models are never entered
        automatically - an unexpected switch must never cost money.

        Models this account has just proved exhausted are skipped: repeating a
        known-failing model costs a slow round trip and never succeeds.
        """
        primary = parse_model_ref(request.model or self._config.model)
        if primary is None and self._chain.refs:
            primary = self._chain.refs[0]
        if primary is None:
            primary = self._resolve_model(request)

        plan = list(self._chain.plan(primary))
        for alternative in free_tier_alternatives(self._catalogue_pairs(), exclude=primary):
            if alternative not in plan:
                plan.append(alternative)

        usable = [ref for ref in plan if not self._is_exhausted(ref)]
        if usable:
            return tuple(usable)
        raise GatewayRateLimited(
            "The model service is rate limited on every model it offers right now. "
            "It was checked a moment ago - try again in a few minutes."
        )

    def _is_exhausted(self, ref: ModelRef) -> bool:
        """True when this model is known to be out of quota right now."""
        if self._account_exhausted(ref):
            return True
        failures = self._model_failures.get(ref.id)
        if failures is None:
            return False
        count, first_seen = failures
        if time.monotonic() - first_seen > EXHAUSTED_COOLDOWN_SECONDS:
            self._model_failures.pop(ref.id, None)
            return False
        # The model failed on more than one account: it is out of quota for
        # this setup, not just for one account.
        return count >= MODEL_FAILURE_LIMIT

    def _account_exhausted(self, ref: ModelRef) -> bool:
        account = self._account_id()
        if not account:
            return False
        until = self._exhausted.get((account, ref.id))
        if until is None:
            return False
        if until <= time.monotonic():
            self._exhausted.pop((account, ref.id), None)
            return False
        return True

    def _account_id(self) -> str:
        """The account the service is currently using ("" when unknown)."""
        if self._active_account:
            return self._active_account
        store = self._credential_store()
        try:
            credentials = store.list()
        except GatewayError:
            return ""
        for credential in credentials:
            if credential.active:
                self._active_account = credential.id
                break
        return self._active_account

    def _mark_exhausted(self, ref: ModelRef) -> None:
        """Remember that this model is out of quota."""
        account = self._account_id()
        if account:
            self._exhausted[(account, ref.id)] = time.monotonic() + EXHAUSTED_COOLDOWN_SECONDS
        count, first_seen = self._model_failures.get(ref.id, (0, time.monotonic()))
        self._model_failures[ref.id] = (count + 1, first_seen)
        logger.info(
            "model %s is out of quota (failure %d); skipping it for %d seconds",
            ref.id,
            count + 1,
            EXHAUSTED_COOLDOWN_SECONDS,
        )

    def _catalogue_pairs(self) -> list[tuple[str, str]]:
        """(provider, model id) pairs the service advertises."""
        try:
            entries = self.registry.all()
        except GatewayError:
            return []
        return [(entry.provider, entry.id) for entry in entries if entry.enabled]

    def _credential_store(self) -> CredentialStore:
        if self._rotator is None:
            self._rotator = CredentialStore(self._request)
        return self._rotator

    def _rotate_credential(self) -> bool:
        """Ask the service to use another stored account. True when it did.

        When the app has its own key pool (``gateway.account_keys``), only
        those accounts are ever used - the service may know more, but the app
        stays inside the pool the owner configured.
        """
        if not self._config.rotate_credentials:
            return False
        pool = configured_account_keys(self._config)
        store = self._credential_store()
        try:
            credentials = store.list()
        except GatewayError as exc:
            logger.info("cannot read stored accounts: %s", exc.message)
            return False
        for credential in credentials:
            if not credential.id or credential.id in self._tried_credentials:
                continue
            if pool and credential.key not in pool:
                continue  # not one of the accounts the app may use
            if credential.active:
                # The account in use is the one that just failed.
                self._tried_credentials.add(credential.id)
                continue
            try:
                store.activate(credential.id)
            except GatewayError as exc:
                logger.info("cannot switch account: %s", exc.message)
                continue
            self._tried_credentials.add(credential.id)
            self._active_account = credential.id
            logger.info("switched to another account (label=%s)", credential.label)
            return True
        return False

    def _register_configured_keys(self) -> None:
        """Store the app's own keys with the service, once, without duplicates."""
        if self._keys_registered:
            return
        keys = configured_account_keys(self._config)
        if not keys:
            self._keys_registered = True
            return
        self._keys_registered = True
        store = self._credential_store()
        for key in keys:
            try:
                store.register(key)
            except GatewayError as exc:
                logger.info("could not register an account key: %s", exc.message)

    # -- request composition ----------------------------------------------
    @staticmethod
    def _compose_prompt(request: ChatRequest) -> str:
        instructions = [SYSTEM_PROMPT]
        conversation: list[str] = []
        for message in request.messages:
            if message.role == "system":
                # App rules (identity, privacy) belong in the instruction
                # block, never as an "Assistant" line.
                if message.content.strip():
                    instructions.append(message.content.strip())
                continue
            role = "User" if message.role == "user" else "Assistant"
            conversation.append(f"{role}: {message.content.strip()}")
        lines = ["\n".join(instructions), "", "Conversation:", *conversation, "Assistant:"]
        return "\n".join(lines)

    def _resolve_model(self, request: ChatRequest) -> ModelRef:
        ref = parse_model_ref(request.model or self._config.model)
        if ref is not None:
            return ref
        try:
            return self.registry.select("chat")
        except GatewayNotConfigured:
            original = self._catalog_error
            if original is not None:
                # Re-raise the catalogue failure in its own class so auth problems
                # stay NotConfigured and reachability problems stay Unavailable.
                raise type(original)(
                    "No model is configured and the model catalogue could not be read: "
                    f"{original.message}"
                ) from original
            raise GatewayNotConfigured(
                "No model is configured. Set gateway.model in config.toml, or request one "
                "per message, so the right model is used."
            ) from None
        except GatewayError as exc:  # noqa: BLE001 - defensive, never leak raw
            raise GatewayNotConfigured(
                f"No model is configured and the catalogue could not be read: {exc.message}"
            ) from exc

    # -- session flow ------------------------------------------------------
    def _create_session(self, ref: ModelRef) -> str:
        payload = {
            "title": DEFAULT_TITLE,
            "location": {"directory": self._location},
            "model": ref.as_api(),
        }
        body = self._request("POST", "/api/session", payload)
        session_id = str(((body.get("data") or {}).get("id")) or "").strip()
        if not session_id:
            raise GatewayProtocolError(
                "OpenCode did not return a session id. The server may be a different version."
            )
        logger.debug("opencode session %s created for %s", session_id, ref)
        return session_id

    def _send_prompt(self, session_id: str, prompt: str) -> float:
        body = self._request("POST", f"/api/session/{session_id}/prompt", {"text": prompt})
        data = body.get("data") or {}
        created = (data.get("time") or {}).get("created")
        return float(created) if isinstance(created, (int, float)) else time.time() * 1000.0

    def _wait_for_idle(self, session_id: str) -> None:
        self._request(
            "POST",
            f"/api/experimental/session/{session_id}/wait",
            timeout=self._timeout,
        )

    def _await_assistant_reply(self, session_id: str, prompted_at: float) -> dict[str, Any]:
        deadline = time.monotonic() + self._timeout
        while True:
            body = self._request("GET", f"/api/session/{session_id}/message")
            messages = body.get("data") or []
            candidates = [
                message
                for message in messages
                if isinstance(message, dict)
                and message.get("type") == "assistant"
                and self._created_at(message) >= prompted_at - 1
            ]
            if candidates:
                return max(candidates, key=self._created_at)
            if time.monotonic() >= deadline:
                raise GatewayTimeout(
                    "OpenCode accepted the prompt but produced no assistant reply in time."
                )
            time.sleep(0.2)

    @staticmethod
    def _created_at(message: dict[str, Any]) -> float:
        created = (message.get("time") or {}).get("created")
        return float(created) if isinstance(created, (int, float)) else 0.0

    def _to_response(self, message: dict[str, Any], requested: ModelRef) -> ChatResponse:
        parts: list[str] = []
        for item in message.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        text = "".join(parts).strip()
        detail = message.get("error")
        if not text:
            if _is_quota_error(detail):
                raise GatewayRateLimited(
                    "The model service refused the request because a quota or "
                    "rate limit was reached."
                )
            suffix = f" Provider detail: {detail}" if detail else ""
            raise _EmptyReply(
                "OpenCode returned an assistant message with no text." + suffix
            )

        model = message.get("model") or {}
        used = ModelRef(
            id=str(model.get("id") or requested.id),
            provider=str(model.get("providerID") or requested.provider),
        )

        finish = str(message.get("finish") or "stop")
        if message.get("error"):
            reason = "error"
        elif finish == "length":
            reason = "length"
        else:
            reason = "stop"

        tokens = message.get("tokens") or {}
        usage: dict[str, int] = {}
        for key in ("input", "output", "reasoning"):
            value = tokens.get(key)
            if isinstance(value, int):
                usage[key] = value

        return ChatResponse(text=text, model=str(used), finish_reason=reason, usage=usage)

    def _delete_session(self, session_id: str) -> None:
        try:
            self._request("DELETE", f"/api/session/{session_id}", timeout=5.0)
        except GatewayError as exc:
            logger.debug("could not delete session %s: %s", session_id, exc.message)

    # -- model catalogue ---------------------------------------------------
    def _load_registry(self) -> ModelRegistry:
        preferred = self._config.model or None
        try:
            body = self._request("GET", "/api/model", timeout=min(self._timeout, 10.0))
        except GatewayError as exc:
            self._catalog_error = exc
            logger.warning("model catalogue unavailable (%s); using config only", exc.message)
            ref = parse_model_ref(self._config.model)
            return ModelRegistry.from_ids([ref.id], provider=ref.provider) if ref else ModelRegistry([])
        else:
            self._catalog_error = None
        models = body.get("data")
        if not isinstance(models, list):
            raise GatewayProtocolError("OpenCode model catalogue had an unexpected shape.")
        return ModelRegistry.from_api(models, preferred=preferred)

    # -- HTTP --------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        url = self._base_url + path
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", self._auth)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")

        wait = timeout or self._timeout
        try:
            with urllib.request.urlopen(request, timeout=wait) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            message = _error_message(raw_error)
            if exc.code in (401, 403):
                raise GatewayNotConfigured(
                    "OpenCode rejected the service password. Restart OpenCode, then retry - "
                    "the password is read from the service registration file."
                ) from exc
            if exc.code == 429:
                raise GatewayRateLimited("OpenCode is rate limiting requests.") from exc
            if exc.code == 503:
                raise GatewayUnavailable(message) from exc
            if exc.code == 404:
                raise GatewayProtocolError(
                    f"OpenCode has no endpoint at {path}. The server version may not match "
                    "this adapter (verified against 2.0.29)."
                ) from exc
            raise GatewayUnavailable(
                f"OpenCode returned HTTP {exc.code} for {path}: {message}"
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise GatewayTimeout(
                f"OpenCode did not answer within {wait:.0f}s."
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise GatewayTimeout(f"OpenCode did not answer within {wait:.0f}s.") from exc
            raise GatewayUnavailable(
                f"Cannot reach the OpenCode service at {self._base_url}: {exc.reason}. "
                "Start it with `opencode serve`, then retry."
            ) from exc
        except OSError as exc:
            raise GatewayUnavailable(
                f"Cannot reach the OpenCode service at {self._base_url}: {exc}."
            ) from exc

        if not raw:
            return {}
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayProtocolError(
                "OpenCode returned a response this build could not parse as JSON."
            ) from exc
        if not isinstance(body, dict):
            raise GatewayProtocolError("OpenCode returned an unexpected JSON payload.")
        return body

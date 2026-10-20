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
from scholarpath.gateway.registry import ModelRef, ModelRegistry, parse_model_ref

logger = logging.getLogger("scholarpath.gateway.opencode")

AUTH_USER = "opencode"
PASSWORD_ENV = "OPENCODE_SERVICE_PASSWORD"
DEFAULT_TITLE = "ScholarPath chat"

SYSTEM_PROMPT = (
    "You are ScholarPath AI, a scholarship assistant for students.\n"
    "Rules you must follow:\n"
    "- Never invent scholarships, deadlines, funding amounts, URLs or eligibility criteria.\n"
    "- If you do not know or cannot verify something, say so plainly.\n"
    "- This build has no web search and no document access yet. Do not claim to have\n"
    "  researched anything or to have checked official sources.\n"
    "- Keep answers short and useful. Ask for missing facts instead of guessing."
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
        prompt = self._compose_prompt(request)
        ref = self._resolve_model(request)
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

    # -- request composition ----------------------------------------------
    @staticmethod
    def _compose_prompt(request: ChatRequest) -> str:
        lines = [SYSTEM_PROMPT, "", "Conversation:"]
        for message in request.messages:
            role = "User" if message.role == "user" else "Assistant"
            lines.append(f"{role}: {message.content.strip()}")
        lines.append("Assistant:")
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
        if not text:
            detail = message.get("error")
            suffix = f" Provider detail: {detail}" if detail else ""
            raise GatewayProtocolError(
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

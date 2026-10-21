"""OpenAI-compatible gateway.

Talks to any endpoint that speaks ``POST {base_url}/chat/completions`` - a
local router, a self-hosted server, or a hosted provider. This is the second
way the chat can be served besides the local OpenCode service, and it is the
one that works when a model is free but the OpenCode account quota is spent.

Rules that hold for every provider in this package:

- One request is one completion. Nothing is streamed, nothing is faked.
- A failure is a typed ``GatewayError``; the chain moves on instead of
  inventing an answer.
- The secret never leaves this object: it is only used in the Authorization
  header, and never logged.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
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
from scholarpath.gateway.credentials import configured_keys
from scholarpath.gateway.failover import KeyPool, ModelChain
from scholarpath.gateway.registry import ModelRef, parse_model_ref

logger = logging.getLogger("scholarpath.gateway.openai")


class _EndpointRejection(GatewayProtocolError):
    """The endpoint refused the request shape (HTTP 400).

    Another model may still serve the request, so the chain moves on.
    """

    retryable = True


class OpenAICompatibleGateway:
    """ModelGateway for an OpenAI-compatible HTTP endpoint."""

    name = "openai"

    def __init__(self, config: GatewayConfig) -> None:
        base = (config.api_base_url or "").strip().rstrip("/")
        if not base:
            raise GatewayNotConfigured(
                "gateway.api_base_url is required when provider = 'openai'. "
                "Point it at an OpenAI-compatible endpoint, for example "
                "http://127.0.0.1:4182/v1."
            )
        parsed = urlparse(base)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise GatewayNotConfigured(
                f"Invalid api_base_url: {base!r}. Expected http:// or https://."
            )

        self._base_url = base
        self._endpoint = f"{base}/chat/completions"
        self._timeout = float(config.timeout_seconds)
        # The endpoint has its own model list when one is configured, so the
        # same config can hold an OpenCode chain and an endpoint chain.
        if config.api_model.strip() or config.api_models:
            self._primary = parse_model_ref(config.api_model)
            self._chain = ModelChain.from_ids(config.api_models)
        else:
            self._primary = parse_model_ref(config.model)
            self._chain = ModelChain.from_ids(config.models)
        self._pool = KeyPool(configured_keys(config))
        self._max_attempts = int(config.failover_attempts)
        logger.info("openai-compatible gateway ready at %s", base)

    # -- public ------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return self._base_url

    def complete(self, request: ChatRequest) -> ChatResponse:
        plan = self._chain.plan(parse_model_ref(request.model or "") or self._primary)
        if not plan:
            raise GatewayNotConfigured(
                "No model is configured for this endpoint. Set gateway.model or "
                "gateway.models in config.toml."
            )

        attempts = 0
        last_error: Exception | None = None
        for ref in plan:
            while attempts < self._max_attempts:
                attempts += 1
                key = self._pool.current()
                try:
                    return self._complete_with(ref, key, request)
                except GatewayRateLimited as exc:
                    last_error = exc
                    logger.info("endpoint refused %s (%s)", ref.id, exc.message)
                    if key is None:
                        break  # no key to rotate - try the next model
                    self._pool.mark_tried(key)
                    continue
                except GatewayNotConfigured as exc:
                    last_error = exc
                    if key is None:
                        raise
                    # A rejected key may be a bad key - try the next one.
                    self._pool.mark_tried(key)
                    logger.info("endpoint rejected a key; trying the next one")
                    continue
                except GatewayError as exc:
                    if not exc.retryable:
                        raise
                    last_error = exc
                    break  # next model

        if isinstance(last_error, GatewayRateLimited):
            raise GatewayRateLimited(
                "The model endpoint is rate limited on every model and key tried "
                f"({attempts} attempts). Wait a few minutes and try again."
            ) from last_error
        if isinstance(last_error, GatewayError):
            raise last_error
        raise GatewayUnavailable("No model answered the request.")

    # -- request -----------------------------------------------------------
    def _complete_with(
        self,
        ref: ModelRef,
        key: str | None,
        request: ChatRequest,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": ref.id,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        try:
            body = self._post(payload, key)
        except _EndpointRejection as exc:
            # Some models only speak the OpenAI Responses API.
            if "responses" not in exc.message.casefold():
                raise
            logger.info("model %s needs the responses endpoint", ref.id)
            body = self._post_responses(payload, key)
        return self._to_response(body, ref)

    def _post_responses(self, payload: dict[str, Any], key: str | None) -> dict[str, Any]:
        messages = payload.get("messages") or []
        instructions = "\n\n".join(
            str(message.get("content") or "")
            for message in messages
            if message.get("role") == "system"
        )
        conversation = [
            {"role": message.get("role"), "content": message.get("content")}
            for message in messages
            if message.get("role") != "system"
        ]
        body: dict[str, Any] = {
            "model": payload.get("model"),
            "input": conversation,
            "max_output_tokens": payload.get("max_tokens", 1024),
            "stream": False,
        }
        if instructions:
            body["instructions"] = instructions
        # No temperature here: several models on this API refuse the
        # parameter outright, and the default is the one they expect.
        return self._post_json(f"{self._base_url}/responses", body, key)

    def _post(self, payload: dict[str, Any], key: str | None) -> dict[str, Any]:
        return self._post_json(self._endpoint, payload, key)

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        key: str | None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        if key:
            request.add_header("Authorization", f"Bearer {key}")

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise self._map_http_error(exc) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise GatewayTimeout(
                f"The model endpoint did not answer within {self._timeout:.0f}s."
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise GatewayTimeout(
                    f"The model endpoint did not answer within {self._timeout:.0f}s."
                ) from exc
            raise GatewayUnavailable(
                f"Cannot reach the model endpoint at {self._base_url}: {exc.reason}."
            ) from exc
        except OSError as exc:
            raise GatewayUnavailable(
                f"Cannot reach the model endpoint at {self._base_url}: {exc}."
            ) from exc

        if not raw:
            raise GatewayProtocolError("The model endpoint returned an empty response.")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayProtocolError(
                "The model endpoint returned a response this build could not parse."
            ) from exc
        if not isinstance(body, dict):
            raise GatewayProtocolError("The model endpoint returned an unexpected payload.")
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "the endpoint reported an error")
            if "rate limit" in message.lower() or "quota" in message.lower():
                raise GatewayRateLimited("The model endpoint reported a rate limit.")
            raise GatewayProtocolError(f"The model endpoint reported an error: {message}")
        return body

    @staticmethod
    def _map_http_error(exc: urllib.error.HTTPError) -> GatewayError:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - the body is best effort only
            raw = ""
        message = raw[:300]
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    message = str(error.get("message") or message)
                elif isinstance(error, str):
                    message = error
                elif payload.get("message"):
                    message = str(payload["message"])
        except json.JSONDecodeError:
            pass

        if exc.code in (401, 403):
            return GatewayNotConfigured(
                f"The model endpoint rejected the configured key (HTTP {exc.code})."
            )
        if exc.code == 402:
            return GatewayRateLimited(
                "The model endpoint reports no credit left for this key."
            )
        if exc.code == 429:
            return GatewayRateLimited("The model endpoint is rate limiting requests.")
        if exc.code == 404:
            return GatewayProtocolError(
                "The model endpoint has no /chat/completions route."
            )
        if exc.code == 400:
            return _EndpointRejection(message)
        if exc.code >= 500:
            return GatewayUnavailable(
                f"The model endpoint returned HTTP {exc.code}: {message}"
            )
        return GatewayProtocolError(
            f"The model endpoint returned HTTP {exc.code}: {message}"
        )

    @staticmethod
    def _to_response(body: dict[str, Any], requested: ModelRef) -> ChatResponse:
        if "choices" not in body and "output" in body:
            return OpenAICompatibleGateway._to_responses_response(body, requested)

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise GatewayProtocolError("The model endpoint returned no choices.")
        first = choices[0]
        if not isinstance(first, dict):
            raise GatewayProtocolError("The model endpoint returned an unexpected choice.")
        message = first.get("message")
        content = ""
        if isinstance(message, dict):
            content = str(message.get("content") or "")
        if not content:
            content = str(first.get("text") or "")
        if not content.strip():
            raise GatewayProtocolError("The model endpoint returned an empty reply.")

        finish = str(first.get("finish_reason") or "stop")
        reason = "length" if finish == "length" else "stop"

        usage_raw = body.get("usage") or {}
        usage: dict[str, int] = {}
        if isinstance(usage_raw, dict):
            for key, target in (
                ("prompt_tokens", "input"),
                ("completion_tokens", "output"),
                ("total_tokens", "total"),
            ):
                value = usage_raw.get(key)
                if isinstance(value, int):
                    usage[target] = value

        used = str(body.get("model") or requested.id)
        return ChatResponse(text=content.strip(), model=used, finish_reason=reason, usage=usage)

    @staticmethod
    def _to_responses_response(body: dict[str, Any], requested: ModelRef) -> ChatResponse:
        """Read an OpenAI Responses API answer."""
        parts: list[str] = []
        for item in body.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") not in (None, "message"):
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    parts.append(content["text"])
        text = "".join(parts).strip()
        if not text:
            raise GatewayProtocolError("The model endpoint returned an empty reply.")

        usage_raw = body.get("usage") or {}
        usage: dict[str, int] = {}
        if isinstance(usage_raw, dict):
            for key, target in (
                ("input_tokens", "input"),
                ("output_tokens", "output"),
                ("total_tokens", "total"),
            ):
                value = usage_raw.get(key)
                if isinstance(value, int):
                    usage[target] = value

        status = str(body.get("status") or "completed")
        reason = "length" if status == "incomplete" else "stop"
        used = str(body.get("model") or requested.id)
        return ChatResponse(text=text, model=used, finish_reason=reason, usage=usage)

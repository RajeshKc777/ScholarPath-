"""Account (credential) rotation for the OpenCode adapter.

OpenCode stores its integration credentials itself and exposes them over
HTTP:

- ``GET  /api/credential``                -> every stored credential, with its secret
- ``POST /api/credential``                -> store a credential
- ``POST /api/credential/{id}/activate``  -> make one the active credential
- ``DELETE /api/credential/{id}``         -> remove one

The app uses this to rotate accounts when a model quota is exhausted: the same
idea as the OpenCode key-rotator plugin, but driven by the app's own failed
requests. Secrets are never written to logs, the UI, or the repository.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scholarpath.config import GatewayConfig

logger = logging.getLogger("scholarpath.gateway.credentials")

# (method, path, payload, timeout) -> parsed JSON body
RequestFn = Callable[[str, str, dict[str, Any] | None, float | None], dict[str, Any]]

DEFAULT_INTEGRATION = "opencode"

# Comma separated list of keys, used when the config file carries none.
KEY_ENV = "SCHOLARPATH_API_KEYS"
# Console keys for the model service's account rotation.
ACCOUNT_KEY_ENV = "SCHOLARPATH_ACCOUNT_KEYS"


def _keys(values: list[str], env_name: str) -> tuple[str, ...]:
    keys = [key.strip() for key in values if key and key.strip()]
    for key in os.environ.get(env_name, "").split(","):
        cleaned = key.strip()
        if cleaned and cleaned not in keys:
            keys.append(cleaned)
    return tuple(keys)


def configured_keys(config: GatewayConfig) -> tuple[str, ...]:
    """Keys for the OpenAI-compatible endpoint.

    These live in the user's local config or environment - never in the
    repository, the logs, or the student UI. A provider profile names its own
    environment variable so keys are not shared between unrelated endpoints.
    """
    env_name = (config.api_keys_env or KEY_ENV).strip() or KEY_ENV
    return _keys(config.api_keys, env_name)


def configured_account_keys(config: GatewayConfig) -> tuple[str, ...]:
    """Console keys the app registers with the model service for rotation."""
    return _keys(config.account_keys, ACCOUNT_KEY_ENV)


@dataclass(frozen=True, slots=True)
class Credential:
    """One stored account credential."""

    id: str
    label: str
    integration: str
    active: bool
    key: str

    def masked(self) -> str:
        """A safe identifier for logs - never the secret itself."""
        if len(self.key) <= 12:
            return "***"
        return f"{self.key[:6]}...{self.key[-4:]}"


class CredentialStore:
    """Read and rotate the credentials of one integration."""

    def __init__(self, request: RequestFn, integration: str = DEFAULT_INTEGRATION) -> None:
        self._request = request
        self._integration = integration

    def list(self) -> list[Credential]:
        """Every stored credential of this integration."""
        body = self._request("GET", "/api/credential", None, 15.0)
        entries = body.get("data")
        if not isinstance(entries, list):
            return []
        found: list[Credential] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            integration = str(entry.get("integrationID") or "")
            if integration != self._integration:
                continue
            value = entry.get("value")
            key = ""
            if isinstance(value, dict):
                key = str(value.get("key") or "")
            found.append(
                Credential(
                    id=str(entry.get("id") or ""),
                    label=str(entry.get("label") or ""),
                    integration=integration,
                    active=bool(entry.get("active")),
                    key=key,
                )
            )
        return found

    def activate(self, credential_id: str) -> bool:
        """Make a stored credential the active one. True when the switch stuck."""
        if not credential_id:
            return False
        self._request("POST", f"/api/credential/{credential_id}/activate", None, 15.0)
        logger.info("activated another account credential (id=%s)", credential_id)
        return True

    def register(self, key: str, label: str = "ScholarPath") -> str | None:
        """Store a key with the service. Returns the credential id, or None.

        A key that is already stored is not duplicated - the existing entry is
        reused so the account list stays readable.
        """
        cleaned = (key or "").strip()
        if not cleaned:
            return None
        for credential in self.list():
            if credential.key == cleaned:
                logger.info("key already stored as %s", credential.masked())
                return credential.id or None
        body = self._request(
            "POST",
            "/api/credential",
            {
                "integrationID": self._integration,
                "label": label,
                "value": {"type": "key", "key": cleaned},
                "activate": False,
            },
            15.0,
        )
        entry = body.get("data") if isinstance(body.get("data"), dict) else body
        credential_id = str((entry or {}).get("id") or "")
        logger.info("registered a new account credential (%s)", cleaned[:6] + "...")
        return credential_id or None

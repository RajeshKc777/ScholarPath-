# ScholarPath AI - failure and provider validation log

Every entry is a **run record**: what was tested, what the provider answered,
what broke, and what was changed. Records are never rewritten - a new run is
appended and the old one stays. Credentials are never written here: keys are
shown only as `present (length)` or as a masked prefix/suffix.

Rules for this file:

- A provider is called **working** only when a real request returned a real
  answer, or when an automated test demonstrates the behaviour offline.
- "Endpoint reachable" is not "provider working".
- Every fix names the source file and line, the root cause, and the regression
  test that now holds it in place.

---

## Run 2 - 2026-10-22 - Gateway stabilisation and provider validation

**Baseline:** `728 passed, 2 warnings in 64.87 s` (pytest, no network).
**After the fixes below:** `733 passed, 2 warnings in 69.70 s`.

Working tree was clean at the start (`ec225eb`); no earlier work was
overwritten or discarded.

### 1. What was tested, and what each provider answered

| Provider / path | Discovery | Auth | HTTP | Model answer | Fallback |
| --- | --- | --- | --- | --- | --- |
| **OpenCode local service** (`127.0.0.1:49374`, discovered from `service.json`) | 45 models in the catalogue, e.g. `deepseek-v4.1-flash-free`, `beam-free`, `flint-40b-free` | service password from the registration file (Basic) | 200 | **OK** - reply "OK", model `opencode/beam-free`, 48.2 s (several quota-limited models + account rotation before it) | the model's own chain; not the profile router |
| **AgentRouter proxy** (`127.0.0.1:4182` -> `agentrouter.org`) | `GET /v1/models` -> 200, catalogue includes `gpt-5.6-sol`, `gpt-6-astra` | key injected by the proxy | 200 (models), 503 (chat, `deepseek-v4-flash`), 400 (chat, `gpt-6.1-sol`) | **OK** - `gpt-6.1-sol` answered "OK" in 3.84 s through the app's adapter (it requires `/v1/responses`; the adapter's fallback handles it) | 503 is retryable, so the router moves to the next profile |
| **AgentRouter direct** (`https://agentrouter.org/v1`) | n/a | user's own `9router` key | **401** `unauthorized client detected` | none | n/a - see finding 4.1 |
| **OpenRouter** (`https://openrouter.ai/api/v1`) | `GET /models` -> 200, 468 models, 17 free (`recursive/flint-v1.0:free`, `nvidia/nemotron-3.5-lightning:free`, ...) | user's own OpenRouter key (from the local OpenCode service) | 200 / 401 (no key) | **OK** - `recursive/flint-v1.0:free` -> "OK", 1.99 s, 9 in / 20 out tokens. A second free model returned 200 with an **empty body** (see finding 4.2); a third returned 502 from its upstream | profile router: 503 -> 503 -> OpenRouter free answered in 1.3 s |
| **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`) | `GET /models` -> 200, 83 models | key present (user env and the local service) - auth passes | **404** `Function '<id>': Not found for account '...'` for every model tried (env key and service key, 4 model ids); `deepseek-ai/deepseek-v4.1-flash` timed out at 60 s | none | none - the account is not entitled to any model (provider-side, not an app defect) |
| **Local Ollama** (`127.0.0.1:11434`) | `GET /api/tags` -> 200, 4 models: `qwen2.5-coder:7b` (4.4 GB), `gemma4:latest` (8.9 GB), `gpt-oss:120b-cloud`, `deepseek-v3.1:671b-cloud` | **none needed** | 200 | **OK** - `qwen2.5-coder:7b` -> "OK" in 52.2 s (cold start, CPU), `gemma4:latest` -> "OK" in 91.8 s | n/a (single profile) |
| **Groq** | - | none on this machine | 401 `Invalid API Key` | none | untested for success (no key) |
| **Gemini** | - | none on this machine | 400 `Missing or invalid Authorization header.` | none | untested for success (no key) |
| **Mistral** | - | none on this machine | 401 `Invalid API Key` | none | untested for success (no key) |
| **xAI** | - | none on this machine | 401 `No credentials presented.` | none | untested for success (no key) |
| **DeepSeek** | - | none on this machine | 401 `Authentication Fails (governor)` | none | untested for success (no key) |

**Working, proven by a real answer:** OpenCode local service, AgentRouter via
the local proxy, OpenRouter (free model), local Ollama.
**Reachable but not entitled:** NVIDIA NIM (404 for every model).
**Reachable, key required, untested for success:** Groq, Gemini, Mistral, xAI,
DeepSeek.
**Not tested at all:** no other provider is configured on this machine.

### 2. Free-only routing (live proof, not only a unit test)

A local HTTP server that records every request stood in for a paid endpoint,
next to a real OpenRouter free profile:

- `free_only = true` -> the recorded endpoint received **0 requests**, the
  free model answered "OK" in 1.8 s.
- `free_only = false` -> the recorded endpoint received the request and
  answered (it was first in the order).

`tests/test_gateway_router.py::test_free_only_mode_never_calls_a_paid_provider`
and
`tests/test_gateway_router.py::test_free_only_mode_without_a_free_profile_says_so`
hold the same rule offline.

### 3. Defects found and fixed

#### 3.1 A profile that cannot serve the request ended the whole turn

- **Live evidence:** profile 1 pointed at an endpoint without
  `/chat/completions` (HTTP 404 `{"error": {"message": "not found"}}`).
  The turn failed with `GatewayProtocolError: The model endpoint has no
  /chat/completions route.` and the **working provider behind it was never
  called**, even though it answered in 1.9 s when tried on its own.
- **Root cause:** `src/scholarpath/gateway/router.py:163` re-raised every
  non-retryable `GatewayError`, so one broken profile aborted the turn.
- **Fix:** the router now skips a profile that cannot serve the request and
  moves to the next one; the error is kept and reported when no profile
  answers. The profile is *not* disabled (a malformed answer may be
  temporary); the reason stays visible in `status()`.
- **Regression tests:**
  `tests/test_gateway_router.py::test_a_profile_that_cannot_serve_the_request_does_not_end_the_turn`,
  `::test_the_error_is_reported_when_no_profile_can_answer`.
- **Re-verified live after the fix:** answer "OK", model
  `recursive/flint-v1.0:free`, 1.9 s.

#### 3.2 A 403 refusal stopped the provider chain

- **Root cause:** `src/scholarpath/gateway/chain.py` treated every
  non-retryable error as fatal for the whole chain. A refusal (HTTP 403)
  answers one provider, not the request - and the live configuration uses
  `provider = "opencode"` with `fallback_providers = ["openai"]`, so a
  refusal on the first provider would have denied the second one.
- **Fix:** the chain moves on for `GatewayForbidden` and reports the refusal
  when no provider answers. A missing or rejected key
  (`GatewayNotConfigured`) still stops the chain, because that is a
  configuration mistake that would repeat.
- **Regression tests:**
  `tests/test_gateway_chain.py::test_a_refused_request_moves_on_to_the_next_provider`,
  `::test_a_refusal_by_every_provider_is_reported`.
- **Re-verified after the fix:** the second provider answered.

#### 3.3 A 400 that means "no key" was reported as a broken request

- **Live evidence:** Gemini without a key answers **HTTP 400**
  `Missing or invalid Authorization header.` - not 401. The adapter mapped
  400 to a generic request-shape rejection, so the app could not tell an
  authentication failure from a bad request.
- **Root cause:** `src/scholarpath/gateway/openai_compat.py:359` mapped every
  400 to `_EndpointRejection`.
- **Fix:** a 400 whose body mentions the Authorization header, an API key or
  authentication is now mapped to `GatewayNotConfigured` (an authentication
  failure). Other 400s keep the old behaviour, including the
  "use /v1/responses" case that the adapter answers with the Responses API.
- **Regression test:**
  `tests/test_openai_compat.py::test_a_missing_authorization_header_is_reported_as_an_auth_failure`.
- **Re-verified live after the fix:** Gemini without a key is now reported as
  `GatewayNotConfigured: ... the key or the Authorization header is missing or
  wrong (HTTP 400)`.

#### 3.4 A local model needs its own timeout (not a code defect, a gap)

- **Live evidence:** `qwen2.5-coder:7b` answered in 52.2 s and
  `gemma4:latest` in 91.8 s on this CPU-only machine. The default timeout
  (30 s; 45 s in the live config) would have failed both.
- **Fix:** the per-profile `timeout_seconds` field already existed; it was
  untested. It is now covered by
  `tests/test_gateway_router.py::test_a_profile_timeout_is_its_own`.
- **Action for the user:** a local Ollama profile needs
  `timeout_seconds = 300` (or higher) in its profile block.

### 4. Findings that are **not** app defects

1. **AgentRouter needs a specific `User-Agent`.** The local proxy
   (`agentrouter-proxy.py`, line 36) injects `User-Agent: opencode/1.17.12`
   because AgentRouter answers 401 for any other client - which is exactly
   what a direct call with `ScholarPath/0.1.0` got. The app must therefore
   reach AgentRouter through the local proxy, or the user must be told that
   the direct route needs the provider's expected client id. **The app was
   not changed to impersonate another client**; it keeps sending its own name.
2. **An OpenRouter free model returned HTTP 200 with an empty body**
   (`xingchen-agi/xing4.0-29b-a4b:free`). The adapter reports that as
   "empty reply"; with fix 3.1 the router now moves on to the next profile
   instead of ending the turn.
3. **NVIDIA NIM returns 404 "Function not found for account" for every model**
   with both available keys. The account is not entitled to inference. The
   adapter maps this to a retryable "model unavailable" (it mentions
   "function"), so the app does not disable the profile - correct, because the
   account may be entitled later.
4. **The OpenCode completion took 48.2 s** because the first models in its
   chain were out of quota and the service rotated accounts and models. That
   is the provider's behaviour, not a hang.

### 5. Security notes (remaining, not fixed in this task)

- `config.toml` stores the OpenCode console keys in plain text
  (`gateway.account_keys`). The file lives in `%APPDATA%\ScholarPath`; moving
  it to Windows Credential Manager was explicitly out of scope for this task.
- The local OpenCode service holds the OpenRouter, NVIDIA and 9router keys.
  The app reads them over loopback with the service password; the validation
  run read them the same way, for one request each, to test those providers.
  No key was printed, logged, or written to this file.
- The app sends `User-Agent: ScholarPath/0.1.0` and never spoofs another
  client's id. Where a provider demands a specific client id, that is done by
  the user's own local proxy, and the limitation is recorded above.
- Profile keys are isolated: a profile reads `SCHOLARPATH_<NAME>_API_KEYS`,
  and the global `SCHOLARPATH_API_KEYS` is never sent to a profile
  (`tests/test_gateway_router.py::test_two_profiles_use_their_own_endpoint_and_key`).

### 6. Still untested / not done

- No successful request for Groq, Gemini, Mistral, xAI or DeepSeek: no
  authorized key exists on this machine. Their endpoints were only reached far
  enough to confirm the key requirement.
- No in-app "Connect" flow, no credential-store migration, no streaming, no
  tool calling - all explicitly out of scope for this task.
- The Ollama service was started for this run and stopped again afterwards;
  the models on disk are unchanged.

---

# ScholarPath AI — Achievements

Last updated: 2026-10-20

What has actually been **built and verified**. A feature appears here only when it
is finished, not when it is started. Each entry names the goal it satisfies
(`Gn` from [goals.md](goals.md)) so the two files stay in sync.

## Definition of done

1. The work exists in the repo (not just in chat).
2. It was run, opened, or checked — there is evidence.
3. The matching goal in `goals.md` is marked `[x]`.

---

## Current state

- Repository: populated and pushed to `https://github.com/RajeshKc777/ScholarPath-`
  (`main`).
- Working app: **yes** — M1 launches with the new light Reddit-orange dashboard;
  from M2 the chat runs **live through the local OpenCode service** (adapter +
  registry + routing), falls back to the stub with honest copy when selected.
- Licence: proprietary, source-available, view-only (`LICENSE`).
- Tests: **56 passing** (`pytest`, ~9 s) — 25 original, 31 new for the gateway.
- Next milestone: **M3** (G203) — profiles, document ingestion, OCR.

---

## Log (newest first)

### 2026-10-20 — A8 · Milestone 2 complete — OpenCode gateway adapter

**Satisfies:** G202, G104 (partially — model registry + task routing), G103

- `src/scholarpath/gateway/opencode.py` — the real adapter against the local
  OpenCode background service, protocol verified beforehand:
  - discovery: registration file `~/.local/state/opencode/service.json`
    (`XDG_STATE_HOME` / `LOCALAPPDATA` / explicit override),
  - auth: `Basic base64("opencode:<password>")`,
  - one completion = one session: `POST /api/session` → `POST .../prompt` →
    `POST /api/experimental/session/.../wait` → `GET .../message` (newest
    assistant message after the prompt timestamp) → `DELETE` best-effort,
  - honest failures: `GatewayNotConfigured` (no registration / bad password),
    `GatewayRateLimited` (429), `GatewayUnavailable` (503 / unreachable),
    `GatewayTimeout` (deadline or no assistant reply), `GatewayProtocolError`
    (unknown shape / unparseable reply).
- `src/scholarpath/gateway/registry.py` — `ModelRegistry`/`ModelEntry` loaded
  from `GET /api/model`, with deterministic task routing: chat (configured then
  first enabled), classify (cheapest), extract (vision-capable then largest
  context), research (tool-capable then largest context).
- `src/scholarpath/config.py` + `config.example.toml` — new `[gateway]`
  `base_url` / `service_file` / `location_dir` (empty = auto-discovery);
  `base_url` requires the password via `OPENCODE_SERVICE_PASSWORD`. No secrets
  in source control.
- `src/scholarpath/ui/` — status pill turns green "Live · opencode" with the
  subtitle "Model replies are live … research still to come"; stub stays honest
  "Offline · stub".
- Factory dispatches `provider = "opencode"` — the M1 "arrives in Milestone 2"
  exit-code path is replaced by the real adapter.

Verified, not assumed:

- Fake OpenCode server on loopback: full session round-trip (auth checked,
  system rules + history in the prompt, session deleted exactly once), and
  every error class mapped without crashing (wrong password, 429, 503, 404,
  500, corrupt JSON, unreachable port, wait timeout, missing assistant reply).
- Live check against the real service: `python -c … complete(...)` → model
  replied **"gateway live"**, `opencode/beam-free`, finish `stop`, usage
  recorded; catalogue read and routed.
- `pytest` → **56 passed** (25 original unchanged, 31 new).

Known limits:

- `gateway.retries` accepted but not acted on (recorded as a decision — no blind
  retry of billable completions).
- No streaming: the reply appears once, after the wait completes (~seconds on
  the free model).
- Free-tier one-shot endpoint (`/api/experimental/generate`) is refused from
  outside OpenCode; the session path is what works.

---
### 2026-10-20 — A7 · Light dashboard UI implemented + Reddit-orange recolour

**Satisfies:** G108 (partially — chat UX), G120 (new)

- Rebuilt the M1 Qt shell as a light "AI dashboard"
  (`src/scholarpath/ui/main_window.py`, `theme.py`):
  - white sidebar with real milestones (disabled items carry M3/M4/M5/M6 badges),
  - orange-gradient welcome card "Hello." with wired quick-action tiles,
  - light-blue assistant cards + orange gradient user bubbles, hover "Copy",
  - academic-profile panel showing real state ("Not set up yet", `—` values,
    0% complete — nothing invented),
  - "What works today" capability card, slim status strip with gateway/model/
    message count and elided config path,
  - `Segoe MDL2 Assets` glyphs for nav/icons (verified installed).
- Second pass (same day): user-shared Reddit-style recolour — **palette swapped
  in `theme.py` only, structure untouched**: `#FF4500`-family orange accents,
  white chrome, orange user bubble / send button, blue assistant bubble.
- Evidence: screenshots at 1440×900 empty + conversation and 1120×760 — no
  clipping, chips/tiles wrap via `FlowLayout`, `pytest` **25 passing**, app
  launches. `docs/screenshot.png` replaced with the live Reddit-colour build.
- Honesty carried over: every unbuilt feature is labelled with its milestone;
  clicking a future tile posts "Not available in this build — … arrives in
  Milestone N." Settings opens the real config folder (`QDesktopServices`).

Known limits: the earlier muted/editorial brief (`antigravityUI.md`) now describes
the *old* look — kept as historical contract, superseded by `goals.md` §19a and
`theme.py`. Suggestion chips were replaced by the four action tiles. Chat copy
still comes from the deterministic stub; nothing pretends research happened.

---

### 2026-10-20 — A6 · Stitch design prompts + rendered references

**Satisfies:** G119

- `stitch-prompt.md` — project setup prompt, three screen prompts (empty state,
  conversation + error, read-only settings), an iteration table for common drift,
  and guardrails.
- Generated in Stitch project `projects/551533196934687083` (`ScholarPath AI UI`):
  - empty state → `screens/d548bb6780ae4bcbbb7703972a44f5f0`
  - conversation + error → `screens/7714757823734a27a758c521bff36c0a`
- Committed as `docs/stitch-empty-state.png` (600×480 preview) and
  `docs/stitch-conversation.png`. Cleaned one render pass: removed an invented
  header label, a stray fourth chip, a "CONTEXT" control, latency metrics, and
  placeholder paths.

Verified: both screenshots downloaded and inspected; they match the brief's palette,
hierarchy and honesty rules (no scholarships, no fake progress).

Known limits: Stitch renders a web approximation, not Qt. Labels truncate at this
preview size, and the settings screen was prompted but not generated. The PNGs are a
visual reference — `antigravityUI.md` remains the contract.

---

### 2026-10-20 — A5 · UI hand-off brief for Antigravity

**Satisfies:** G118

- `antigravityUI.md` — self-contained brief for an external agent to rebuild the
  presentation layer without breaking the project's honesty rules.
- Contents: read-first list, exact M1 inventory (files, signals, `Turn` fields),
  8 hard constraints, design tokens (palette, type scale, spacing, radius, motion),
  layout measurements, six screens/states, copy rules, accessibility, suggested
  module split, acceptance checklist, deliverables, explicit out-of-scope list.
- Key guardrail: no fabricated scholarships, no simulated progress, no dead
  controls, no QtWebEngine/QML, no new dependencies.

Verified: file exists in the repo root; every referenced path and symbol matches
the current source (`ChatController` signals, `Turn` fields, `config_path()`,
`scholarpath.__version__`).

Known limit: it is a document, not an implementation. The UI it describes does not
exist until Antigravity (or this agent) builds and verifies it.

---

### 2026-10-20 — A4 · Public presentation + proprietary licence

**Satisfies:** G116, G117

- `LICENSE` — custom all-rights-reserved, source-available notice. Grants viewing
  and personal non-commercial evaluation only; forbids copying, modification,
  redistribution, sublicensing, and derivative works; states that contributions
  and pull requests are not accepted.
- `README.md` — rebuilt: badge row (status, Python, Qt, tests, licence),
  full-width screenshot, "why this exists" principle table, milestone status
  table, what-works / what-it-refuses-to-do split, collapsible quick start,
  configuration reference, architecture map, quality-gate table, privacy section,
  licence block, non-affiliation disclaimer.
- `docs/screenshot.png` — real capture of the running window (1550 × 1025) with a
  two-turn conversation. Not a mock-up.

Verified: screenshot rendered from the live app, image committed, README links
resolve to files that exist (`LICENSE`, `docs/screenshot.png`, `goals.md`,
`achievements.md`, `config.example.toml`).

Known limit: a licence controls legal reuse, not GitHub mechanics. A public repo
can still be forked by others; push access is controlled by collaborator
settings. Visibility ≠ writability — that is recorded in `goals.md` §16.

---

### 2026-10-20 — A3 · Milestone 1 complete

**Satisfies:** G201, plus G112 (partially), G115

Built (24 files, 1 837 insertions):

| Area | File(s) |
| ---- | ------- |
| Entry point, CLI flags | `src/scholarpath/app.py`, `__main__.py` |
| Strict config (TOML + pydantic) | `src/scholarpath/config.py`, `config.example.toml` |
| Gateway contract + stub | `src/scholarpath/gateway/{base,stub,factory}.py` |
| Chat state + threading | `src/scholarpath/ui/chat_controller.py` |
| Qt window | `src/scholarpath/ui/main_window.py` |
| Logging (no payloads) | `src/scholarpath/logging_setup.py` |
| Tests | `tests/test_{config,gateway,chat_controller}.py` |

Verified, not assumed:

- `pytest` → **25 passed**.
- Window renders correctly on the real Windows platform (screenshot inspected):
  welcome block, user turn, assistant turn, status bar all separated.
  First render was broken — `insertHtml` collapsed blocks into one line; fixed by
  re-rendering the whole transcript document.
- `scholarpath --version` → `ScholarPath AI 0.1.0`; console entry point works.
- `scholarpath --init-config` → writes the template, exit `0`.
- `provider = "opencode"` → exit `3` with an explicit "arrives in Milestone 2"
  message; no silent fallback to the stub.
- `timeout_seconds = 0` → exit `2` with the offending field named.
- Startup off-screen and on-screen, with a live message send, both clean.

Known limits:

- No network, no model, no research. The stub says so in every reply.
- `.venv` is 260 MB and lives inside OneDrive (sync cost) — recorded as a decision.
- UI is smoke-tested manually; automated widget tests are not in place yet.

---

### 2026-10-20 — A2 · Environment baseline verified

**Satisfies:** G115 (verify before building), G103 (technology direction)

| Item | Finding |
| ---- | ------- |
| Default `python` | 3.11.9 — `...\Programs\Python\Python311\python.exe` |
| Also installed | 3.13 (`py -3.13`), plus the `py` launcher |
| pip (system) | 26.2.1 |
| git | 2.55.0 |
| uv | not installed |
| `mcp` (system) | 1.25.0 installed but **broken** — `ModuleNotFoundError: mcp.server.fastmcp.resources.templates` |

Project venv (fresh, isolated): Python 3.11.9, PySide6-Essentials 6.12.0 (Qt 6.12.0),
pydantic 2.14.1, pytest 9.1.1 — all import-tested.

**Implication:** a project venv is mandatory; the global env cannot be trusted.

---

### 2026-10-20 — A1 · Goals / achievements tracking process

**Satisfies:** G2, G3

- `goals.md` — full product specification (G101–G115) with requirement register,
  milestone table, decision log, dependency checklist, open questions.
- `achievements.md` — this file.
- `AGENTS.md` — project memory carrying the maintenance rule.
- Global config (`~/.config/opencode/AGENTS.md`) points at this project's rule.

**Evidence:** files present in `C:\Users\LOQ\OneDrive\Desktop\ScholarPath`.

---

## Not yet achieved

- G101, G102, G104–G111, G114 — product capabilities beyond the M2 gateway.
- Milestones G203–G207.

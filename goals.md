# ScholarPath AI — Goals

Last updated: 2026-10-20
Owner: LOQ
Status: **scope defined** — specification supplied by the owner on 2026-10-20.

This file is the single source of truth for **what the system must do**. Every new
requirement is added here first (dated, new `Gn` ID), then built, then marked `[x]`
and logged in [achievements.md](achievements.md). Nothing is deleted.

Status key: `[ ]` not started · `[~]` in progress · `[x]` done (has an `An` entry).

---

## Requirement register

| ID | Section | Requirement | Status |
| -- | ------- | ----------- | ------ |
| G2 | 0 | Maintain `goals.md` + `achievements.md`, updated on every change | `[x]` |
| G3 | 0 | Documentation updated in the same session as the change | `[x]` |
| G101 | 1 | Product vision: AI scholarship discovery + academic guidance, Windows desktop, local-first | `[ ]` |
| G102 | 2 | Core principles: accuracy, official sources, explainability, routing, modularity, privacy, cost, UX, quality | `[ ]` |
| G103 | 3 | Technology direction (Python, PySide6, FastAPI, Pydantic, SQLite, OpenCode, MCP, OCR, PyInstaller, pytest) | `[~]` |
| G104 | 4 | AI orchestration: 6 modular agents, model registry, task-based routing, failure handling | `[ ]` |
| G105 | 5 | Conversational onboarding, academic profiles, document upload + confirmed extraction | `[ ]` |
| G106 | 6 | Scholarship research with source-verification hierarchy and structured records | `[ ]` |
| G107 | 7 | Deterministic eligibility engine and explainable ranking | `[ ]` |
| G108 | 8 | Desktop chat UI: onboarding, results, filters, comparison, saved list, settings | `[ ]` |
| G109 | 9 | MCP + tool integration with untrusted-input handling and read-only research default | `[ ]` |
| G110 | 10 | SQLite data architecture, privacy, deletion controls, secrets handling | `[ ]` |
| G111 | 11 | Installation workflow and Windows packaging | `[ ]` |
| G112 | 12 | Development workflow and code-quality rules | `[~]` |
| G113 | 13 | Milestones M1–M7, each with acceptance criteria | `[~]` |
| G114 | 14 | Definition of success (10-step student journey) | `[ ]` |
| G115 | 15 | Agent operating instructions (inspect → summarise → plan → verify → build smallest step) | `[x]` |
| G116 | 16 | Public read-only repository: proprietary licence, no external contributions | `[x]` |
| G117 | 17 | Presentation-grade README: screenshot, status, quick start, licence block | `[x]` |
| G118 | 18 | External UI hand-off brief (`antigravityUI.md`) for Antigravity | `[x]` |
| G119 | 19 | Stitch design prompt + rendered reference screens | `[x]` |
| G120 | 19a | Light dashboard UI shell implemented (then Reddit-orange colour-only recolour) | `[x]` |
| G202 | 13 | M2 OpenCode gateway adapter: discovery, session inference, registry, routing, error handling | `[x]` |

---

## 1. Project vision (G101)

Build **ScholarPath AI**, an intelligent, AI-powered scholarship discovery and
academic guidance platform that helps students identify **legitimate** scholarship
opportunities worldwide, based on academic qualifications, study goals, language
proficiency, financial need, and destination preferences.

- Initially a **local-first desktop application for Windows**; runnable from source
  during development, distributable as a standalone executable later.
- Must support bachelor's graduates, master's applicants, postgraduate students,
  and PhD scholars.
- Long-term: a personalized academic research assistant — discover funding,
  evaluate eligibility, compare universities, prepare applications.

## 2. Core product principles (G102)

Priority order for every design decision:

- Accuracy over quantity of recommendations.
- Official, verifiable sources over unverified search results.
- Explainable eligibility assessments over unsupported AI predictions.
- Dynamic model selection instead of a single LLM.
- Modular architecture: new models, agents, tools, providers are additive.
- Privacy-first handling of student information and academic documents.
- Cost-efficient execution, using compatible free models where available.
- Clean, intuitive chat interface for non-technical students.
- Maintainable, testable, secure, production-oriented code.

**Hard rule:** never fabricate scholarships, university requirements, funding
amounts, deadlines, source URLs, or eligibility criteria.

## 3. Technology direction (G103)

Python-first.

| Layer | Choice |
| ----- | ------ |
| Logic + orchestration | Python |
| Desktop UI | PySide6 |
| Internal API boundary (when needed) | FastAPI |
| Data validation | Pydantic |
| Persistence (initial) | SQLite |
| Model gateway | OpenCode (primary) — behind an adapter |
| Tool integration | Model Context Protocol (MCP) |
| Document extraction | OCR / parsing libraries |
| Packaging | PyInstaller or equivalent |
| Testing | pytest |

Constraints:

- All external dependencies sit behind clearly defined interfaces.
- Business logic must not be coupled to OpenCode, one LLM provider, or one MCP server.
- Verify external interfaces and current behaviour **before** implementation.
- Do not assume free model access is unlimited, or that the OpenCode runtime ships
  with the application.

## 4. AI orchestration and dynamic model routing (G104)

Central orchestration layer: interprets the request, plans tasks, selects models,
invokes permitted tools, validates results. Mixture-of-experts **style** routing —
no custom MoE neural network.

Agent responsibilities (shared models allowed; one LLM per agent not required):

1. **Intent Router** — classify request, choose workflow.
2. **Research Agent** — discover opportunities, retrieve official sources.
3. **Academic Profile Agent** — extract/normalize student info from forms + documents.
4. **Eligibility Agent** — compare profile against requirements.
5. **Ranking Agent** — rank by eligibility, funding, destination, preferences, deadlines.
6. **Explanation Agent** — present results with evidence and next steps.

Model registry entries: identifier, provider, capabilities, tool-calling support,
availability, cost notes, fallback options. Routing is driven by **task
requirements**, not arbitrary switching. Use lightweight models for classification,
capable models for research, OCR/vision for extraction, deterministic Python for
eligibility math.

Handle unavailable models, rate limits, timeouts, invalid responses, provider
failures gracefully. Never silently replace a failed research run with fabricated
results.

## 5. Onboarding and academic profiles (G105)

Conversational onboarding that asks only what is needed:

- Intended study level; current/completed qualifications.
- Degree title, discipline; GPA/grading scale/percentage.
- Graduation year and academic history.
- Nationality and other eligibility-relevant facts.
- Preferred countries and universities.
- Language proficiency: IELTS / PTE / TOEFL or equivalent.
- GRE / GMAT and other standardized tests where applicable.
- Research interests and intended specialization.
- Funding requirements and estimated budget.
- Intake preferences and timeline.
- Professional, research, or extracurricular experience.

Document support: marksheets, transcripts, degree certificates, language-test reports.

- Extract what is available, mark uncertain values, ask for confirmation.
- Never assume a GPA scale, invent missing scores, or convert grades without a
  documented conversion policy.
- Users can correct extracted data and update profiles at any time.

## 6. Scholarship research and source verification (G106)

Source priority:

1. Official university scholarship/admissions sites.
2. Official government scholarship portals.
3. Official programme administrators.
4. Recognized institutional and research-funding organizations.
5. Other reputable sources **for discovery only**, then verified against official sources.

Per scholarship, capture where available: title + institution; country; eligible
nationalities; degree levels and disciplines; academic requirements; language/test
requirements; tuition coverage; stipend, travel, insurance, extra benefits; opening
date and deadline; intake/cycle; required documents; official info URL; official
application URL; retrieval timestamp; last-verified timestamp; verification status;
missing information.

- Discovery ≠ verification. A search result alone is not evidence for a critical claim.
- Prefer the current application cycle. Flag expired, unverified, conflicting, or
  unavailable information explicitly.
- If a fact cannot be verified, state the limitation instead of guessing.

## 7. Eligibility assessment and ranking (G107)

Deterministic eligibility engine over structured profile + structured requirements.

Requirement states: **satisfied · not satisfied · unknown · requires manual verification**.
Distinguish confirmed eligibility from potential eligibility; never call a student
eligible while critical requirements are unknown.

- Apply hard requirements **before** ranking.
- Ranking criteria (configurable): eligibility fit, funding completeness, academic/
  subject alignment, destination preference, language-test compatibility, deadline
  feasibility, application effort, student priorities.
- No invented numerical admission or award probabilities.
- Explain relevance, satisfied requirements, uncertainties, and next actions.
- Distinguish fully funded / tuition waiver / partial / other funding types.

## 8. Chat interface and UX (G108)

Desktop chat with:

- Conversational onboarding; profile management; document uploads.
- Research progress and task status.
- Scholarship result cards with official source links and eligibility explanations.
- Country, funding, and deadline filters.
- Scholarship comparison; saved scholarships/shortlists.
- Application preparation checklists.
- Settings for model providers and preferences.
- Clear error messages and retry options.

Responsive while long research tasks run. Evidence displayed close to the claims it
supports. Do not expose model/MCP/agent internals to students.

## 9. MCP and tool integration (G109)

Use MCP where interoperability genuinely helps. Candidate tool categories: web
search and official-source discovery; page retrieval and structured extraction;
academic document processing; scholarship database queries; profile operations;
comparison and application planning.

- Business logic independent of MCP transport — internal Python functions testable directly.
- Read-only research tools by default.
- Web content, downloads, and uploads are **untrusted input**: never let them
  override system instructions, read arbitrary local files, or execute commands.
- Explicit user approval for sensitive external actions or anything that modifies
  external accounts or submits applications.

## 10. Data architecture and privacy (G110)

SQLite first, schema designed for later PostgreSQL migration.

Entities: student profiles · academic documents · scholarships · source records ·
eligibility evaluations · scholarship matches · saved opportunities · research runs ·
application tasks.

- Student documents stay local by default.
- Minimize personal data sent to model providers.
- No sensitive documents or credentials in logs.
- No secrets in source control or packaged resources; ship a config template with
  no real credentials.
- Deletion controls for profiles, documents, and research history.
- Make it clear when external services are used and when data leaves the device.

## 11. Installation and distribution (G111)

- Development: git clone + standard Python project config, Windows-focused docs.
- Setup must check Python and runtime deps, create/use an isolated environment,
  install deps, init local storage, configure gateway access, validate settings,
  and report failures clearly.
- Later: Windows executable/installer. User data and config kept separate from
  bundled files.
- Packaging does **not** imply OpenCode, model runtimes, or hosted model access are
  included — document extra runtime requirements.

## 12. Development workflow and code quality (G112)

Inspect the repository and understand the architecture before implementing. Do not
replace working components or add unnecessary dependencies without justification.

- Clear module boundaries, single-responsibility components.
- Type hints on public functions and important interfaces.
- Explicit schema validation for external input.
- Structured logging with no sensitive data.
- Automated tests for business logic and integrations; mock model and web calls.
- Configuration separate from implementation; explicit exception handling.
- No hardcoded secrets, credentials, or machine-specific paths.
- Document significant architectural decisions; keep setup/run docs current.
- No single oversized module. Build incrementally, test each milestone, keep the
  app working throughout.

## 13. Milestones (G113)

| ID | Milestone | Scope | Acceptance criterion | Status |
| -- | --------- | ----- | -------------------- | ------ |
| G201 | M1 | Repository, project config, desktop shell, configuration handling, basic chat | App launches from a clean checkout; config validates; chat round-trips against a stubbed gateway; tests pass | `[x]` |
| G202 | M2 | OpenCode gateway adapter, model registration, task routing, error handling | Registry loads; routing picks model per task; unavailable model/rate limit/timeout handled without crash | `[x]` |
| G203 | M3 | Profiles, document ingestion, OCR, user-confirmed extraction | Profile persisted; marksheet parsed; low-confidence fields flagged; user corrections saved | `[ ]` |
| G204 | M4 | Source discovery, official-source verification, structured scholarship storage | Scholarship records carry source URLs + timestamps + verification status; unverifiable fields marked unknown | `[ ]` |
| G205 | M5 | Deterministic eligibility, explainable ranking, cited recommendations | Eligibility states correct on fixtures; ranking reproducible; every claim cites a source | `[ ]` |
| G206 | M6 | MCP integrations, comparison, saved opportunities, checklists | MCP tools usable behind adapter; comparison and saved items persist | `[ ]` |
| G207 | M7 | Security review, testing, performance, Windows packaging | Packaged app runs on clean Windows; test suite green; no secrets in bundle | `[ ]` |

Rule: no milestone starts before the previous one has a working, testable result.

## 14. Definition of success (G114)

Prototype succeeds when a student can:

1. Launch the desktop app.
2. Configure and verify a supported model gateway.
3. Describe education goals through chat.
4. Enter academic info or upload a marksheet.
5. Review and correct extracted info.
6. Request scholarships for a chosen level, destination, funding preference.
7. Receive relevant opportunities from legitimate sources.
8. See official links, deadlines, funding details, eligibility explanations.
9. Understand what is satisfied, missing, or uncertain.
10. Save scholarships and retrieve them later.

It must handle missing information, outdated sources, and provider failures honestly.
A smaller reliable assistant beats a large multi-agent system with unverified output.

## 15. Instructions for the AI coding agent (G115)

1. Inspect the repository and identify what already exists.
2. Summarize current structure and architectural gaps.
3. Propose a minimal plan aligned with the milestones.
4. Identify dependencies and external interfaces that need verification.
5. Begin with the smallest useful, testable milestone.
6. Explain significant design decisions; record architectural changes.
7. Never claim something works unless it was implemented and verified.

Do not build all planned features at once. Keep the architecture extensible, the
implementation practical, and the objective unchanged: helping students find
legitimate, relevant, realistically attainable scholarships.

## 16. Licensing and repository access (G116)

- The repository is **public and read-only**: the owner pushes, nobody else does.
  External contributions and pull requests are not accepted.
- Code is **source-available but proprietary** — `LICENSE` grants viewing and
  personal non-commercial evaluation only; copying, modification, redistribution,
  sublicensing, and derivative works require written permission.
- A licence governs legal reuse. It cannot prevent GitHub forking of a public
  repository, and write access is controlled by collaborator settings, not by the
  licence. Keeping the repo public therefore means: visible to all, editable by
  nobody but the owner, reusable by nobody without permission.
- Copyright holder line must be reviewed by the owner (currently "Rajesh Kc").

## 17. Public presentation (G117)

- `README.md` is the shopfront: badge row, screenshot, honest status table,
  quick start, architecture, quality gates, privacy, and the licence block.
- Screenshot lives at `docs/screenshot.png` and must show the real UI, never a
  mock-up of features that do not exist.
- The README states the current milestone's limits in plain language, so nobody
  can mistake the shell for a working scholarship engine.

## 18. External UI hand-off (G118)
- `antigravityUI.md` is the brief handed to the Antigravity coding agent to rebuild
  the presentation layer. It restates the M1 inventory, design tokens (palette,
  type scale, spacing), screen-by-screen states, copy rules, accessibility, and an
  acceptance checklist.
- It is a **derivative** of this specification. If the two ever disagree, this file
  wins and the brief is corrected.
- The brief's hard constraints are non-negotiable: no fabricated scholarships, no
  simulated work, no new runtime dependencies, no web view (Essentials only).
- UI work delivered against the brief is accepted only when its §8 checklist is
  satisfied **and** `pytest` stays green; then it is logged here as an `An` entry.

## 19. Design reference (G119)

- `stitch-prompt.md` holds the copy-paste prompts for Google Stitch: a style block
  plus one prompt per screen (empty state, conversation + error, settings), and a
  table of iteration prompts for common drift.
- Rendered screens are committed as `docs/stitch-empty-state.png` and
  `docs/stitch-conversation.png` (Stitch project `551533196934687083`).
- These are **references, not specifications**. Tokens in this file and
  `antigravityUI.md` override anything the renderer invents; the generated HTML is
  never shipped (the app is Qt, not a web view).
- Observed drift to audit every render: invented micro-labels, invented metrics
  ("latency", "speed"), extra chips, truncated labels, and a God-object "context"
  control in the composer. Each render needs a cleanup pass before use.

## 19a. Implemented dashboard design (G120, 2026-10-20)

- The M1 shell was rebuilt as a light "AI dashboard": navy → white sidebar kept to
  accompany the reference, gradient welcome card, four quick-action tiles, chat
  column, academic-profile panel, slim status strip.
- Structure mirrors the user's dashboard reference, **minus every fabricated
  element**: profile fields read "Not set up yet" with `—` values, tiles and nav
  items carry their milestone badge (M3/M4/M5/M6), disabled items explain when they
  arrive, and clicking a future feature posts an honest status message instead of
  pretending to work.
- 2026-10-20 (second pass): the user supplied a Reddit-style recolour of the same
  layout and asked for **colour only, no structural changes**. Palette is now
  white chrome + orange accents (`#FF4500` family), light-blue assistant bubbles,
  orange user bubble, orange send button. All tokens live in
  `src/scholarpath/ui/theme.py`; `main_window.py` structure is untouched by the
  recolour.
- Layout still overrides the mock where honesty demands it: no fake scholarships,
  no invented "80% profile complete", no notification badge, no search bar that
  searches nothing.

## 19b. OpenCode gateway adapter (G202, 2026-10-20)

- `src/scholarpath/gateway/opencode.py` talks to the **local OpenCode background
  service**: endpoint + password read from its registration file
  (`~/.local/state/opencode/service.json`), `Authorization: Basic
  base64("opencode:<password>")`. One completion = one short-lived session:
  create → prompt → wait → read newest assistant message → delete.
- The `/api/experimental/generate` one-shot endpoint **rejects free-tier calls
  from outside OpenCode**; the session path is the one that works and is what the
  official client uses.
- `registry.py` holds the model catalogue (`ModelRegistry`, `ModelEntry`) and the
  task router: chat (configured/first enabled), classify (cheapest), extract
  (vision → largest context), research (tools → largest context). Deterministic,
  ties broken by model id.
- Every failure is a typed `GatewayError` (NotConfigured / RateLimited /
  Timeout / Unavailable / ProtocolError). The UI surfaces the message; nothing
  is retried blindly or replaced with a fabricated answer.
- Config: `[gateway] base_url / service_file / location_dir` optional overrides;
  when `base_url` is set the password must come from `OPENCODE_SERVICE_PASSWORD`
  (never stored in config.toml or source control).
- UI honesty: header pill turns green "Live · opencode" when the gateway is live,
  stays orange "Offline · stub" otherwise; subtitle and composer hint state that
  replies are live but research is still not built.
- Evidence: fake-server test suite (`tests/test_registry.py`,
  `tests/test_opencode_gateway.py`); live round-trip against the real service —
  model replied "gateway live" (usage + finish recorded), 56 tests passing.

---

## Decisions (architectural)

- **2026-10-20 — PySide6-Essentials, not the full PySide6 meta-package.** The
  meta-package drags in WebEngine + Pdf (~400 MB) that nothing uses. Essentials
  provides Core/Gui/Widgets/Network. Measured venv with tests: **260 MB**.
- **2026-10-20 — Config is TOML at `%APPDATA%\ScholarPath\config.toml`,** validated
  with pydantic (`extra="forbid"`). `SCHOLARPATH_HOME` overrides the folder;
  `--config` overrides the file. A missing file is fine, an invalid one is fatal
  (exit code 2).
- **2026-10-20 — Gateway behind the `ModelGateway` protocol.** M1 shipped the stub
  only. From M2, `provider = "opencode"` builds the real adapter: the local
  service is discovered from its registration file, and one completion is a
  short-lived session against the verified 2.0.29 session API. Auth problems map
  to `GatewayNotConfigured`, reachability to `GatewayUnavailable` — still no
  silent downgrade to the stub.
- **2026-10-20 — No auto-retry of completions in M2.** `gateway.retries` exists in
  config but is not acted on yet: retrying a paid completion can double-charge,
  and an orphaned session is worse than one honest error. Revisit only with
  idempotent request tracking.
- **2026-10-20 — Chat UI re-renders one document per turn.** `insertHtml` merges
  adjacent block elements in Qt, collapsing speaker labels into body text;
  rebuilding the document is cheap at chat scale and renders correctly.
- **2026-10-20 — Repository:** `https://github.com/RajeshKc777/ScholarPath-.git`,
  branch `main`, local `.venv` (note: this folder is inside OneDrive, so the venv
  syncs — move it out or exclude it if sync cost matters).
- **2026-10-20 — Proprietary source-available licence, not MIT/Apache/CC.** The
  owner wants the work visible but not reusable. MIT or GPL would grant exactly
  the rights being withheld, so `LICENSE` is a custom all-rights-reserved notice.
- **2026-10-20 — Presentation direction after M1:** the muted editorial brief
  (`antigravityUI.md`) is superseded for the implemented shell by the user's
  references — first a light dashboard temperature, then the Reddit-orange
  recolour (colour-only). Honesty constraints (no fabricated data, milestone
  badges, "no research performed" copy) carry across both passes.
- **2026-10-20 — Icon glyphs use `Segoe MDL2 Assets`** (verified present on this
  Windows build). No icon-webfont dependency is added; a missing font degrades to
  tofu, not crashes.

## Dependencies to verify before building (open)

- [x] OpenCode gateway: **verified 2026-10-20** — local server API (session
      flow), Basic auth from the service registration file, free-tier one-shot
      endpoint rejected, model catalogue at `/api/model`. (`goals.md` §19b,
      [[A8]].)
- [~] PySide6 deployment: Qt 6.12.0 works, `QPlainTextEdit.setPlaceholderText`
      exists (no workaround needed), Essentials-only venv is 260 MB. PyInstaller
      bundling still unproven.
- [ ] OCR stack choice (Tesseract vs RapidOCR/PaddleOCR) — Windows install burden,
      offline behaviour, licence.
- [~] `mcp` Python SDK: globally installed 1.25.0 is broken; must be pinned and
      import-tested inside the project venv before M6.
- [ ] Web research tool: search API availability, terms, cost; whether an MCP search
      server is required.
- [ ] Supported Python version for packaging (3.11 vs 3.13) — 3.11 is the current target.

## Open questions

1. ~~Model gateway: use the local OpenCode HTTP API, or call the inference endpoint
   directly with the stored key?~~ **Resolved 2026-10-20:** local OpenCode HTTP
   API (session flow); the direct inference endpoint refuses free-tier callers.
2. Research breadth target for the prototype: global, or a fixed set of countries?
3. Should the first build ship a seeded scholarship dataset for offline testing?

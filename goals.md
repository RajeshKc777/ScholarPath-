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
| G107 | 7 | Deterministic eligibility engine and explainable ranking | `[x]` |
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
| G203 | 13 | M3 local profile storage, document ingestion (PDF/text/image OCR), verified extraction, user-confirmed merge | `[x]` |
| G204 | 13 | M4 official-page verification: fetch guards, untrusted-content boundary, structured scholarship records with provenance | `[x]` |
| G121 | 20 | The student UI **never** discloses the model or provider - identity probes answered deterministically, leaky replies withheld | `[x]` |
| G122 | 21 | Profile facts stated in chat are captured, confirmed per field, and offered for saving (verbatim-verified only) | `[x]` |
| G123 | 22 | Voice input in chat: speak a prompt or a voice message, speech becomes editable text, then is sent like a normal message (Windows Speech engine, honest privacy copy) | `[x]` |
| G124 | 23 | Voice engine switched to the Python SpeechRecognition library (no Windows speech toggle, no model download); UI copy states that audio is sent to the transcription service | `[x]` |
| G125 | 24 | While the mic is recording, the mic button shows an animated listening ripple; the button stays clickable to stop | `[x]` |
| G126 | 25 | Live voice conversation mode: hands-free listen → reply → speak loop in the chat, with a visible state and a stop control | `[x]` |
| G127 | 26 | Model failover: when the selected model is rate-limited, the chat continues automatically with the next model in a configured chain instead of showing a raw rate-limit error | `[ ]` |
| G128 | 27 | OpenAI-compatible gateway provider: the chat can be served directly by any OpenAI-compatible endpoint (e.g. a local router that serves DeepSeek), with its own key and model chain | `[ ]` |
| G129 | 28 | Key rotation inside the app: console keys are registered with the model service and rotated between accounts when a model quota is exhausted | `[ ]` |
| G130 | 29 | Spoken replies use a natural neural voice (free Edge neural TTS, no API key) with the offline Windows voice as automatic fallback; the transcript auto-scrolls as the conversation grows | `[x]` |
| G131 | 29 | Replies read like a person wrote them: no markdown symbols (bold asterisks, `--`, headings, tables) in the chat bubble or the voice, and the model is asked to answer in plain, warm, conversational prose | `[x]` |
| G132 | 29 | Live voice mode survives a failed reply: the app says what happened out loud and keeps listening, and stopping a capture really releases the microphone | `[x]` |
| G133 | 29 | The spoken reply must actually be audible: the neural audio is played as a WAV file through the Windows audio engine (the route the local voice uses), and if playback does not run the app falls back to the offline voice instead of silence | `[ ]` |
| G134 | 30 | Find scholarships on a site the student trusts: the app lists the scholarship/funding links published on a page (same site only, no guessing), and one click reads and verifies the chosen page | `[x]` |
| G135 | 31 | Let the chat use MCP tools: when a read-only MCP tool is configured and enabled, the chat can call it during a turn, with tool output treated as untrusted data, size-capped and never obeying instructions inside it | `[ ]` |
| G136 | 32 | Web search in the chat: the app can run a keyless web search when the student needs current results, answer from those results with the pages named, and treat every result as untrusted data | `[x]` |
| G137 | 33 | Saving the profile must be unmistakable: the save is confirmed on screen with the time, a failed save says so, and the side card always mirrors what is really stored locally | `[x]` |

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

*Implemented in M5 (see [[goals]] §19f and [[achievements]] A12):*
requirement states map to `satisfied / not_satisfied / unknown / needs checking
(manual)`; hard requirements are compared before any ordering; ranking is a
documented deterministic key, not a score; verdicts never say "eligible" and
never show probabilities. Funding-type ranking policy is deliberately deferred
(funding is descriptive in records, not a stochastic input).

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
| G203 | M3 | Profiles, document ingestion, OCR, user-confirmed extraction | Profile persisted; marksheet parsed; low-confidence fields flagged; user corrections saved | `[x]` |
| G204 | M4 | Source discovery, official-source verification, structured scholarship storage | Scholarship records carry source URLs + timestamps + verification status; unverifiable fields marked unknown | `[x]` |
| G205 | M5 | Deterministic eligibility, explainable ranking, cited recommendations | Eligibility states correct on fixtures; ranking reproducible; every claim cites a source | `[x]` |
| G206 | M6 | MCP integrations, comparison, saved opportunities, checklists | MCP tools usable behind adapter; comparison and saved items persist | `[x]` |
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
- UI honesty: header indicator turns into a small green "● Live" chip when the
  gateway is live, an orange "● Offline" chip otherwise; subtitle and composer
  hint state that replies are live but research is still not built. Provider
  names are never shown in the student-facing UI (logs only).
- Evidence: fake-server test suite (`tests/test_registry.py`,
  `tests/test_opencode_gateway.py`); live round-trip against the real service —
  model replied "gateway live" (usage + finish recorded), 56 tests passing.

---

## 19c. Student-facing copy pass (G120 follow-up, 2026-10-20)

- **Provider-neutral UI.** Students never see which company or model serves a
  reply: the status chip is just "● Live"/"● Offline", the status strip reads
  "chat: live"/"chat: offline", and assistant turn headers show only
  "SCHOLARPATH" (the served model stays in the logs). Technical names
  (`opencode`, model ids) live in `config.toml`, logs and this document.
- **"Soon" badges, not "M3/M4/M6".** Sidebar items, quick-action tiles, the
  profile card and the "What works today" rows carried opaque Mx badges. They
  now read "Soon"; the milestone number moved into the tooltip ("Coming in
  Milestone 3 — not available in this build"), so the roadmap survives without
  jargon.
- **Live chip layout fix.** The status label was stretched to the 76px top-bar
  height by the layout (a big coloured block). It is now aligned vertically and
  sizes to its text; the live state is transparent with green text, no
  background.
- Verified with rendered screenshots of the real window (off-screen, real
  fonts) in empty and two-turn states; 57 tests passing.

---

## 19d. Profile + document pipeline (G203, 2026-10-20)

- **Storage** (`src/scholarpath/storage.py`): thread-safe SQLite (`scholarpath.db`
  in `%APPDATA%\ScholarPath`). Documents keep filename, mime, full extracted text,
  OCR flag, warnings and an extraction JSON that records both what was proposed
  and what the user applied. Saved via a `BEGIN IMMEDIATE` write lock.
- **Profile model** (`src/scholarpath/profiles.py`): strict Pydantic model,
  no `extra` guessing; `merge_confirmed(profile, values)` merges only the fields
  the user accepted and **never wipes a known value with None**; completion is a
  share of 12 nothing-invented fields.
- **Ingestion** (`src/scholarpath/documents.py`): PDF text layer via `pypdf`,
  plain text/markdown passthrough, images via **Windows OCR** (Foundation.Media.Ocr,
  pywin32+winsdk direct async call inside the app — no Tesseract install, works
  with a QApplication present). Problems are warnings on the result, never crashes.
- **Extraction** (`src/scholarpath/extraction.py`): one gateway call proposes a
  JSON field map; every proposed value must appear **verbatim** (case-insensitive)
  in the document text or it is marked "not found in document" with the reason.
  Nothing unverifiable is applied silently.
- **UI**: a "My Profile" page (local-only form, Save/Clear, honest feedback) and a
  "Documents" page (Upload → local parse → proposal → per-value confirm rows with
  ✓ found / ? not-found markers → "Apply checked values to profile"). The degree
  combo accepts **free text** (e.g. "Bachelor of Science" from a transcript) so an
  extracted title is displayed and re-saved verbatim instead of being wiped by the
  literal-only dropdown — verified by a form round-trip check. The composer
  attach button and the "Upload Documents" tile now open the documents page; the
  sidebar entries are live ("Soon" badges remain only on Scholarships and Saved
  Opportunities, M4/M6). The right-panel profile card mirrors the stored state
  (name, degree, GPA, IELTS, countries, completion %).
- **Window integration**: the body is a `QStackedWidget` (chat / profile /
  documents); page switching keeps the sidebar highlight, top-bar title and status
  strip in step; the database closes on exit and ingest threads are cancelled.
- **Evidence**: 20 extraction tests + 16 storage tests; live end-to-end — OCR read
  a synthetic marksheet image, the configured gateway proposed 4 fields, all four
  verified verbatim against the OCR text, merged to a 33% profile and round-tripped
  through SQLite; a UI-level check confirmed unticked fields stay empty after
  Apply. Off-screen renders verified both pages visually. **84 pytest tests passing.**

---

## 19e. Official-page verification (G204, 2026-10-20)

- **Honest scope decision first:** this build has **no web-search tool**, so
  there is no "find me scholarships" step. Discovery ≠ verification is enforced
  structurally: the user supplies the **official** page URL; the app verifies it.
  Automatic candidate search stays open pending a search-tool decision
  ([A11], open question).
- **Retrieval** (`src/scholarpath/sources.py`): stdlib-only (no new dependency)
  — http/https only (file:/ftp:/credentials refused), non-HTML content refused,
  2 MB byte cap with an explicit "truncated" warning, redirect final-URL
  tracking, script/style stripped to text, sha256 + retrieval timestamp captured.
- **Untrusted-input boundary** (early G109 discipline): fetched page text is
  data only; the extraction prompt wraps it in `<<<PAGE>>>` markers and tells
  the model to ignore instructions inside it. Tests assert page content sits
  inside the marked block.
- **Verification** (`src/scholarpath/research.py`): the model proposes a
  16-field scholarship schema (G106 fields: title, institution, country,
  nationalities, levels, funding, deadline, intake, documents, application URL…);
  every proposal must be **verbatim** in the page text (`verbatim_in_source`,
  digit-group-tolerant) or it is reported as unknown. Nothing unverifiable is
  stored. `parse_model_json` is now parameterized per allowed field set.
- **Storage**: `scholarship` table with requested/final URL, retrieval
  timestamp, page sha256, data JSON (values + unknown + warnings), status
  `page-verified`; full CRUD.
- **UI**: a fourth page ("Scholarship Pages"): URL input → Read page → draft
  card with per-value confirm rows (✓ found on page / ? not found) →
  "Save checked values" → stored record card listing provenance, saved values
  and the explicitly-unknown fields. Sidebar "Scholarships" and the
  "Find Scholarships" tile are live with honest labels ("Official pages you
  paste", "no automatic search").
- **Evidence**: 21 new tests (fake HTTP server covering every fetch guard +
  draft verification + storage round-trip), **105 pytest tests passing**; live
  end-to-end — fetched `chevening.org/scholarships/` (7,043 chars), the gateway
  proposed 6 fields, **all verbatim** (title, institution, host country,
  nationalities, degree level, funding coverage), each asserted verbatim against
  the page text and round-tripped through SQLite.

---

## 19f. Deterministic eligibility engine (G205, 2026-10-20)

- **Engine** (`src/scholarpath/eligibility.py`): pure rule-based Python — no
  model calls, no probabilities. Five requirement checks against the stored
  verbatim record values + local profile: nationality (whole-entry list match,
  word-boundary safe), degree level (keyword reading of both sides), language
  (IELTS/TOEFL thresholds with alternative pathways), academic GPA (compared
  **only** on a matching, explicitly stated scale — mismatch is "needs checking",
  never silently converted), deadline (only unambiguous month-name dates parsed;
  numeric `01/02/2026`-style dates are never guessed).
- **States**: `satisfied / not_satisfied / unknown / manual ("needs checking")`
  per G107; every result carries an explanation plus the page evidence it was
  read from (cited source = the record's stored page + field value).
- **Verdict** is honest by construction: "Conflicts with the page as written: …",
  "Potential only — N requirement(s) need checking…", or "No conflicts found on
  the checked requirements — confirm on the official page before applying".
  The word "eligible" never appears in a verdict.
- **Ranking** (`EligibilityReport.rank_key`): documented deterministic tuple —
  conflicts first, then fewest open checks, then most satisfied requirements,
  then title/id tie-break — reproducible, no invented scores. Conflicting
  records still surface (last), never deleted.
- **UI** (`src/scholarpath/ui/eligibility_page.py`, fifth page "Eligibility",
  sidebar + "Check Eligibility" tile live): profile summary line, report cards
  ordered best-first, per-requirement state chips (green/grey/amber/red) with
  explanation + truncated page evidence, "Open source page" deep link, auto
  recompute when profile or records change.
- **Evidence**: 29 engine tests (per-check includes non-match/unknown/ambiguous
  cases; verdict never claims eligibility or shows "%"; deterministic ranking
  asserted twice for reproducibility), **134 pytest tests passing**; live E2E on
  the real Chevening record from M4 — nationality `satisfied` ("The page lists
  Nepal"), degree `satisfied` ("one-year master's degrees"), language/academic/
  deadline honestly `unknown` (the page's verbatim values didn't include
  thresholds), verdict "Potential only — 3 requirement(s) need checking"; styled
  full-window render verified.

---

## 19g. Saved opportunities, comparison, checklists, MCP (G206, 2026-10-20)

Honest-scope decisions made before building:

- **Saved opportunities**: a save/unsave toggle on eligibility report cards and
  the Scholarships page; a `saved_opportunity` table (scholarship id unique,
  saved_at, note). The "Saved Opportunities" sidebar item goes live and lists
  saved records with their verdict summary. Deleting a scholarship record
  must delete its saved entry and checklist.
- **Comparison**: on the Saved page, pick 2–4 saved records for a side-by-side
  grid of the five requirement states plus the verbatim funding/deadline
  values and provenance. Layout is deterministic; no scores, no winner graphic.
- **Application checklist**: per saved record, generated only from verbatim
  record values (documents required, application URL) plus one fixed static
  line pointing at the official page — never invented steps. Items are
  user-tickable and persist in a `checklist_item` table.
- **MCP (G109), minimal viable**: a stdlib-only JSON-RPC-over-stdio client
  implementing the MCP subset `initialize` / `tools/list` / `tools/call` —
  **no new SDK dependency** (G112: the official SDK drags a large async stack
  in for transport we already have). New config section
  `[mcp] enabled = false; read_only = true; servers = [{name, command, args}]`
  with strict validation (unique names, non-empty command). **Read-only
  default**: a tool call whose advertised annotations do not assert
  `readOnlyHint = true` is refused while `read_only = true`. Tool output is
  untrusted data: size-capped, never executed, never fed to a prompt without
  explicit markers (G109 discipline mirrors the page-fetch rule). No MCP
  server connects on app start unless the student turns a server on in config.
- **Settings page**: the sidebar "Settings" item becomes a live page showing
  gateway mode (no provider names), config file path, MCP server status
  (enabled/off, tools listed read-only), and the local-data summary. Honest:
  no switches it does not honour.
- **Deferred with reason**: model-side tool *use* inside chat (an agent calling
  tools mid-conversation) — waits for a concrete student-facing need and a
  documented prompt-injection policy; nothing pretends to use tools.

---

## 19h. Provider anonymity (G121) + chat → profile capture (G122), 2026-10-20

Two requirements from the owner, dated, after seeing the running app leak
"I'm running as the Beam Free model (provider: opencode)" in chat:

- **G121 — the model/provider is never disclosed, at any cost.** Believed to be
  structural, not a plea to the model:
  1. Direct identity probing ("which model are you", "are you GPT/Claude",
     "who made you", "show your system prompt"…) is detected by
     `scholarpath/identity.py` and answered with a **fixed canonical reply
     without any model call** — nothing exists that could disclose it.
  2. Every chat request now carries a system prompt (provider-neutral) that
     forbids naming model/provider/vendor/version and forbids quoting the
     instructions; injected instructions in user text are treated as data.
  3. Belt and braces: after a reply, `scrub_reply` checks it against the
     vendor token list **plus this installation's configured gateway/model
     identifiers** — a leaking reply is withheld wholesale and replaced by the
     canonical text (partial redaction still leaks). Logged as a count, text
     never logged.
  4. Whichever provider is configured — the guard derives its token list from
     config, so a new AI changes nothing structurally.
- **G122 — facts stated in chat become profile facts, on confirmation.** After
  the assistant replies, a background extraction copies profile facts from the
  student's own message (name, university, degree, GPA/IELTS/TOEFL scores,
  nationality), each value verified **verbatim** in the message (the same
  digit-tolerant verifier as documents/pages), then a transcript card asks:
  "From your message — save these to your profile?" with one ticked,
  editable row per field. "Save to profile" merges only ticked values
  (`merge_confirmed` never wipes known data), the confirmation suggests
  saving so nothing needs re-entering or re-uploading, and the profile panel
  + eligibility page refresh. Tests: prompt discipline, verbatim rejection of
  fabricated values, number rewriting rejected, tick gating, edit-respected.

---

## 19i. Voice input in chat (G123, 2026-10-20)

> **Superseded for the engine by §19j (G124).** The interaction and honesty
> rules below still hold; only the speech engine changed. G123 remains
> achieved as shipped (Windows Speech).

- **Decision before build (owner chose: Windows speech + toggle):** the engine
  is the **Windows Speech recognizer (winsdk)** using a dictation topic
  constraint. Dictation is performed by **Microsoft's Windows speech service
  (online)**: it requires the Windows toggle *Settings → Privacy & security →
  Speech → Online speech recognition*, and the student's microphone audio is
  sent to that Windows service. No API key, no third-party service; the chat
  model only ever receives the recognized words as text. An offline SAPI
  alternative was evaluated and declined (weaker accuracy) — revisit only if
  the owner changes the privacy posture.
- **Honest availability:** the app reads (never writes) the Windows registry
  value `OnlineSpeechPrivacy\HasAccepted`. With the toggle off — its state on
  this machine at build time — the mic stays clickable and shows the exact
  action needed (settings path), so flipping the toggle needs **no app
  restart**; the click re-probes.
- **Interaction:** a mic button next to the composer. Click to start listening
  (end-silence stops the capture), click again to force-stop; the recognized
  words land in the composer as **editable text** — the student reviews and
  presses Enter, so a voice message becomes a normal text prompt.
- **Honest degradation:** every Windows failure maps to a plain-language
  student message (toggle off / microphone unavailable / audio quality /
  language pack / timeouts), `0x80045509` included. No recognition — no card,
  no silent nothing. `winsdk` is a justified, verified dependency (G112);
  its modern `windows.media.speech` namespace is absent from the projection,
  so the working `windows.media.speechrecognition` module was probed live
  before any code was written.
- **UI copy says exactly what happens:** the tooltip and the success notice
  name Windows speech recognition (online) — nothing claims the audio is
  understood locally or on this device.

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
- **2026-10-20 — M3 extraction is verify-then-confirm, not trust-then-save.** The
  gateway is allowed to propose field values only; every proposal is checked
  verbatim against the document text before the UI offers it, and the merge into
  the stored profile happens only from rows the user ticked (and may have edited).
  pypdf is preferred over rendering PDFs to images: the text layer is exact, no
  OCR needed when present.
- **2026-10-20 — OCR runs in-process via the app's QApplication.** Windows OCR
  worked fine inside the app process (verified 2026-10-20); the subprocess
  isolation path is kept only as a crash fallback. `pypdf` and `pywin32` are the
  only new dependencies (both pure/local).
- **2026-10-20 — M4 ships verification, not search.** There is no web-search
  tool configured, so discovery-by-search does not exist; the honest increment
  is verified reading of official pages the user pastes. The fetch layer is
  stdlib-only with hard guards (http/https, HTML-only, 2 MB cap, redirect-aware
  provenance). Page text is untrusted data in every prompt. Fields not
  verbatim on the page are recorded as unknown — never normalized, never
  converted, never guessed.
- **2026-10-20 — One giant-country proposal is kept verbatim.** The Chevening
  page test showed the model copying a 150-country list verbatim into
  `eligible_nationalities`. That is correct under "no rewrite without a
  documented conversion policy"; a structured list format needs its own
  documented policy (G105) before any normalisation is added.

## Dependencies to verify before building (open)

- [x] OpenCode gateway: **verified 2026-10-20** — local server API (session
      flow), Basic auth from the service registration file, free-tier one-shot
      endpoint rejected, model catalogue at `/api/model`. (`goals.md` §19b,
      [[A8]].)
- [~] PySide6 deployment: Qt 6.12.0 works, `QPlainTextEdit.setPlaceholderText`
      exists (no workaround needed), Essentials-only venv is 260 MB. PyInstaller
      bundling still unproven.
- [x] OCR stack choice: **resolved 2026-10-20** — Windows built-in OCR
      (Foundation.Media.Ocr via pywin32+winsdk) for images, `pypdf` for PDF text
      layers. No Tesseract/PaddleOCR install burden; offline; degrades to explicit
      warnings when a page has no text or no installed OCR language. (goals.md
      §19d, [[A10]].)
- [~] `mcp` Python SDK: globally installed 1.25.0 is broken; must be pinned and
      import-tested inside the project venv before M6.
- [~] Web research tool: automatic candidate search still needs a search API /
      MCP server decision (cost, terms). Page verification itself is live
      without it — official URLs pasted by the user are fetched and verified
      (`goals.md` §19e, [[A11]]).
- [ ] Supported Python version for packaging (3.11 vs 3.13) — 3.11 is the current target.

## Open questions

1. ~~Model gateway: use the local OpenCode HTTP API, or call the inference endpoint
   directly with the stored key?~~ **Resolved 2026-10-20:** local OpenCode HTTP
   API (session flow); the direct inference endpoint refuses free-tier callers.
2. Research breadth target for the prototype: global, or a fixed set of countries?
3. Should the first build ship a seeded scholarship dataset for offline testing?

---

## 19j. Voice engine swapped to the SpeechRecognition library (G124, 2026-10-20)

- **Owner decision:** drop the Windows Speech engine (it needed the Windows
  "Online speech recognition" toggle and still sent audio to Microsoft).
  Replace it with the standard Python **SpeechRecognition** library (mic via
  PyAudio). This is the "built-in library" route: no Windows setting to flip,
  no model download, no API key.
- **Honest privacy posture:** the library's free `recognize_google` engine
  sends the short audio clip to Google's speech service for transcription
  (needs internet; chat itself is online). The mic tooltip and the status
  notices say exactly that; the chat model still receives only the final text.
- **Unchanged interaction (G123):** one click starts listening, end-silence
  (or 45 s cap) stops it, a second click force-stops; transcript lands in the
  composer as editable text, the student reviews and presses Enter.
- **Unchanged honesty rules:** every failure is a plain-language notice -
  nothing heard, no microphone, service unreachable, stopped - never a silent
  failure and never fabricated text.
- **Dependency note (G112):** `SpeechRecognition` + `PyAudio` replace `winsdk`
  in `pyproject.toml`; both ship Windows/py3.11 wheels, verified by live
  install before coding. `winsdk` is no longer a dependency.
- **Verification:** 207 tests (10 voice-module tests with the library stubbed);
  live capture through the real microphone via the app (15 s no-speech path ->
  honest notice, mic usable again), and the real transcription service proven
  with the library's human-speech sample ("1 2"). Synthetic SAPI audio is
  rejected by the service - not user audio, not a code path.

---

## 19k. Listening ripple on the mic button (G125, 2026-10-20)

- **Owner ask:** after clicking the mic, show a listening-type ripple effect.
- **Implementation:** custom `MicButton` widget (`ui/mic_button.py`), painted
  with QPainter - two orange rings expand outward and fade in a 1.4 s loop,
  the core fills with the accent colour and the glyph turns white. A 16 ms
  QTimer runs **only** while listening; idle is the quiet ghost button with a
  hover tint. No image assets, no new dependency.
- **Bug fixed on the way:** the previous code disabled the mic for the whole
  capture, so "click again to stop" could never work. The button now stays
  enabled while listening; the same click cancels and the ripple stops
  immediately with a "Stopping the microphone..." notice.
- **Honest states:** the ripple runs only while a capture is real; every
  failure or result path ends it and restores the idle look - no animation
  left running, no fake "listening" state.

---

## 19l. Live voice agent (G126, 2026-10-21)

- **Owner ask:** a live voice agent like ChatGPT voice - talk to the app and
  it talks back, hands-free.
- **Shape:** turn-based loop, not full duplex: **Listening -> Thinking ->
  Speaking -> Listening**, started by the "Live voice" control in the top bar
  and ended with the "End" button in the voice bar. The transcript shows every
  spoken turn as a normal chat message, so the conversation stays readable
  and searchable.
- **Engines and API keys (owner question, answered):** speech **output** is
  Windows SAPI through `pyttsx3` - fully offline, no key, no service, audio
  never leaves the device. Speech **input** is the same `SpeechRecognition`
  library as G124 (Google's free web endpoint, no key, internet needed). The
  **model** still comes from the configured local OpenCode gateway - no new
  key was introduced anywhere.
- **Spoken text is cleaned, not raw:** markdown (bold, headings, bullets,
  code ticks) is stripped and bare URLs become "link in the chat" so the voice
  reads sentences. Long replies are truncated at a sentence boundary for
  speech only; the full reply stays in the chat.
- **Honest states:** the voice bar always shows what the app is doing
  (Listening / Thinking / Speaking / Nothing heard yet) - never a fake
  "listening" state. Three empty captures in a row stop the mode with a plain
  notice. Voice mode needs the live model connection; offline it refuses
  with a reason instead of pretending.

---

## 19m. Natural spoken voice + sticky auto-scroll (G130, 2026-10-21)

- **Owner ask:** the spoken reply sounded robotic, and the conversation view
  stopped following the new messages.
- **Voice:** the only voices on this machine were the old SAPI ones (David,
  Zira, Mark), which is why it sounded robotic. The reply is now spoken with
  the free **Edge neural voice** (`edge-tts`, no API key, needs internet) and
  played locally through `winsound`; if the neural engine is missing or the
  network is down, the app **falls back automatically** to the offline
  Windows voice instead of going mute. The voice bar names the engine that
  really spoke - it is never guessed.
- **Auto-scroll:** the transcript follows new messages while the student is at
  the bottom (`should_stick_to_bottom`, 12 px threshold). Scrolling up to
  read earlier turns stops the following, and any pending re-pin is
  cancelled so a late layout change cannot yank the view back down.
  Scrolling back to the bottom re-arms it.
- **Honest cost:** the neural voice sends the reply text to Microsoft's speech
  service (no key, no account). The offline fallback keeps the app usable
  without a network.

---

## 19n. Human-sounding replies + voice that survives failures (G131, G132, 2026-10-21)

- **Owner ask:** the `**` and `--` in the replies made the conversation look
  machine-written, and after the voice change the model stopped speaking in
  live conversation.
- **Plain prose (G131):** two layers.
  - *Ask*: the app-level system prompt and the live gateway prompt now
    require plain sentences with contractions, short paragraphs, and no
    markdown at all - no asterisks, no dash bullets, no headings, no tables,
    no emoji, no filler openings.
  - *Clean up*: `prose.humanize_reply` (new module) turns whatever still
    arrives into plain text for the bubble and the copy button: bold and
    italic markers removed, `--` becomes a real dash, headings and
    horizontal rules dropped, dash bullets become dots, tables become plain
    lines, links keep their label and URL. `prose.speech_text` is the spoken
    variant (one flowing line, links spoken as words, bare URLs as "link in
    the chat"). The model still receives the raw text, so its own context is
    unchanged.
  - The live gateway prompt now keeps the app rules (identity, privacy) in
    the instruction block instead of labelling them as an "Assistant" line.
- **Voice that keeps going (G132):** the app log showed two real problems -
  a failed model reply (quota) and `voice cancel failed: 'Microphone' object
  has no attribute 'stop'`.
  - A failed reply no longer ends voice mode. The app says "Sorry, I couldn't
    get an answer just then. Please ask me again." out loud and keeps
    listening.
  - `cancel_active` now stops the capture the way `speech_recognition` allows
    - by stopping the PyAudio stream - so the microphone is really released
    when a capture is cancelled.
  - The voice loop logs what it does (listening, characters heard, reply
    failed, engine used, speech finished) so a silent voice can be diagnosed
    from the log file instead of guessed at.
  - Voice worker threads are held until they really end, so Qt never destroys
    a running thread.

---

## 19o. Making the neural voice actually audible (G133, 2026-10-21)

- **Owner ask:** the model replied, the voice bar said "Speaking… with the
  neural voice", and no sound came out. Before the neural change, the app
  spoke.
- **Diagnosis.** The app log showed the utterance was handled correctly:
  `speaking with the neural engine` then `speech finished` 3.7 s later. The
  synthesized audio itself was fine (measured: 3.62 s, peak -4.2 dBFS, RMS
  -22.8 dBFS, 62% non-zero samples), so the file was good. The fault was the
  **playback route**: the neural audio was an MP3 played through the Windows
  MCI MP3 device, and on this machine that device accepts the file and runs
  the clock without producing sound. The local Windows voice, which the
  owner could hear, plays a WAV through winmm.
- **Fix.** The neural MP3 is decoded to a WAV file (`miniaudio`) and played
  through winmm - the route that is known to be audible here. If the WAV
  cannot be produced, the MP3 is played directly. If the sound device does
  not really run (playback returns far too early), the neural engine is
  treated as failed and the **offline Windows voice speaks instead**, so the
  app can never be silent.
- **Evidence in the log.** Every utterance now logs the route and the
  timing: `neural voice played .wav (3.62s of audio in 4.09s)`.
- **Still open:** the final audible confirmation is the owner's ear - the
  previous route was reported silent, the new one is mechanically verified
  (Windows rendered the whole 3.62 s stream) but nobody has heard it yet.

---

## 19p. Finding scholarship pages on a trusted site (G134, 2026-10-21)

- **Owner ask:** build the remaining features, starting with the biggest gap:
  the Scholarships page only read URLs the student pasted.
- **What "discovery" means here.** There is still **no open web search** and no
  search API, so the app cannot go looking for scholarships by itself. What it
  can do honestly: take one page the student trusts (a university's
  scholarships page, a government funding portal, a listing page) and list the
  scholarship/funding links that page itself publishes.
- **Rules** (`discovery.py`): http(s) only; same site only (the page's host or
  its subdomains); documents (PDF/DOC/DOCX/...) skipped because the reading
  pipeline only accepts web pages; `mailto:`, `tel:`, `javascript:` and
  in-page anchors ignored; duplicates dropped; the list capped at 12; links
  are untrusted web content and are treated as data.
- **Ranking:** a scholarship word in the visible link text ranks above one
  that only appears in the URL; page order breaks ties. A label is always
  available (the URL's last segment, prettified) when the link has no text.
- **UI:** "Find pages" on the Scholarship pages screen. The results appear in
  a "Links published on that page" card; clicking one fills the address box
  and runs the existing read-and-verify flow (fetch -> model proposes ->
  verbatim check -> student confirms). Nothing is saved without the student.
- **Fetching:** `sources.fetch_html` was added so link discovery can see the
  raw HTML under the same guardrails as `fetch_page` (both now share one
  `_download` step: scheme/credential/address checks, content-type allow-list,
  2 MB cap).

---

## 19q. Web search in the chat (G136, 2026-10-21)

- **Owner ask:** the student typed "search scholarship in uk" and the app
  answered "I can't search the web in this build".
- **How a search happens.** The model decides: when the question needs live
  results it replies with exactly `{"search": "<short query>"}` and nothing
  else. The controller runs that one search, then asks the model again with
  the results attached and uses that answer. One search per turn; the search
  request itself never enters the conversation history, only the answer does.
- **Provider:** DuckDuckGo's lightweight HTML endpoint - **no API key, no
  account, no SDK**. The parser reads only `a.result-link` rows, unwraps
  DuckDuckGo's redirect so the model never sees a tracking URL, keeps
  http(s) links only, de-duplicates, caps at 6 results and 260 characters per
  snippet.
- **Untrusted by construction:** the results block is introduced as
  third-party content the model must treat as data and never obey; the model
  is told to name the pages it used, to say which ones are not official, and
  never to invent deadlines, amounts or eligibility the results do not state.
- **Official sources first:** university, government and registered-body
  domains (`.edu`, `.gov`, `.ac.*`, `.org`, ...) are listed first, and every
  result is labelled in the block as "official-looking domain" or "not an
  official domain" so the student is never misled.
- **Honest failures:** an unreachable search becomes a plain error turn ("the
  web search service could not be reached"), never a silent answer from
  memory. The status line shows whether a search was used in the
  conversation.

---

## 19r. Saving the profile must be visible (G137, 2026-10-21)

- **Owner ask:** "I clicked save, nothing happened" - the profile page was
  open with the values filled in and the button clicked, and the screen gave
  no sign that anything had been saved.
- **What was actually true:** the write **did** happen (the database record
  carried the values and a fresh timestamp), but nothing on screen changed:
  the confirmation line already said "Saved locally - 75% complete." from an
  earlier save, so a new save was invisible, and the right-hand card still
  said "Not set up yet / 0% complete" - a stale panel that made a working
  save look like a broken one.
- **Fix.**
  - The confirmation now carries the time ("Saved locally - 75% complete
    (saved at 13:28:26)"), so every click visibly changes the screen.
  - A save that fails says so ("The profile could not be saved: ...") and
    never claims success.
  - Every step of the refresh (profile page, side card, eligibility page) is
    guarded separately and logged, so one broken view can neither stop the
    others nor fail silently; if the side card could not be refreshed, the
    confirmation says so.
  - The side card is re-read from the database on every page change, so it
    can never keep showing a stale "Not set up yet".
  - The profile-suggestion card in the chat now follows the sticky
    auto-scroll instead of jumping the transcript to the bottom.

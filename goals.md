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
| G202 | M2 | OpenCode gateway adapter, model registration, task routing, error handling | Registry loads; routing picks model per task; unavailable model/rate limit/timeout handled without crash | `[ ]` |
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

---

## Decisions (architectural)

- **2026-10-20 — PySide6-Essentials, not the full PySide6 meta-package.** The
  meta-package drags in WebEngine + Pdf (~400 MB) that nothing uses. Essentials
  provides Core/Gui/Widgets/Network. Measured venv with tests: **260 MB**.
- **2026-10-20 — Config is TOML at `%APPDATA%\ScholarPath\config.toml`,** validated
  with pydantic (`extra="forbid"`). `SCHOLARPATH_HOME` overrides the folder;
  `--config` overrides the file. A missing file is fine, an invalid one is fatal
  (exit code 2).
- **2026-10-20 — Gateway behind the `ModelGateway` protocol.** M1 ships the stub
  only. Selecting `provider = "opencode"` exits with code 3 and an explicit
  message — no silent downgrade to the stub.
- **2026-10-20 — Chat UI re-renders one document per turn.** `insertHtml` merges
  adjacent block elements in Qt, collapsing speaker labels into body text;
  rebuilding the document is cheap at chat scale and renders correctly.
- **2026-10-20 — Repository:** `https://github.com/RajeshKc777/ScholarPath-.git`,
  branch `main`, local `.venv` (note: this folder is inside OneDrive, so the venv
  syncs — move it out or exclude it if sync cost matters).

## Dependencies to verify before building (open)

- [ ] OpenCode gateway: which interface the app calls (local server API vs inference
      endpoint), auth model, rate limits, free-tier constraints.
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

1. Model gateway: use the local OpenCode HTTP API, or call the inference endpoint
   directly with the stored key?
2. Research breadth target for the prototype: global, or a fixed set of countries?
3. Should the first build ship a seeded scholarship dataset for offline testing?

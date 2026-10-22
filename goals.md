# ScholarPath AI — Goals

Last updated: 2026-10-21
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
| G107 | 7 | Deterministic eligibility engine and explainable ranking (funding-type ranking deferred - funding stays descriptive, see §7) | `[x]` |
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
| G138 | 33 | A packaged Windows build: ScholarPath ships as a self-contained app that starts on a clean Windows, keeps all user data and secrets outside the bundle, and passes a security and performance review | `[~]` |
| G139 | 34 | Verbatim verification tolerates spelling differences (unicode, quotes, dashes, hyphenated line breaks, dates compared by value) without ever accepting a value the page does not state | `[x]` |
| G140 | 34 | Privacy switches: voice input, the spoken reply and web search are off by default, each is gated on its own switch, and the Settings page states exactly which third party receives what (the "off by default" half was replaced by G171 on 2026-10-22: the switches are on by default and are now toggles in Settings) | `[x]` |
| G141 | 34 | Official pages are recognised by an exact suffix allowlist on the registrable domain (.edu, .ac.xx, .gov, .gov.xx), plus the student's own trusted_domains - never by a substring | `[x]` |
| G142 | 34 | A Re-check action on saved records: the page is fetched again, the sha256 compared, and changed pages and passed deadlines are flagged on the eligibility and saved pages | `[x]` |
| G143 | 34 | Page fetching is hardened against SSRF: the host is resolved and checked before connecting, private, loopback, link-local and metadata addresses are refused with a typed error, every redirect hop is checked again, and the checked address is the one that is connected to | `[x]` |
| G144 | 35 | A sources registry: a shipped default plus an editable copy in `%APPDATA%`, one entry per official portal (name, base_url, country, trust_level, allowed_path_prefixes, crawl_depth, enabled), seeded only with portals that were verified live | `[x]` |
| G145 | 35 | A crawler: discover pages from sitemap.xml / sitemap index / RSS / Atom and same-site links, obey robots.txt, at most one request per second per host, conditional GET (ETag / If-Modified-Since) with 304 reported as unchanged, a page cap per portal, HTML only, and the same SSRF-guarded fetch the rest of the app uses | `[x]` |
| G146 | 35 | A background catalog job (thread pool) running crawl → extract → verify → save, with a Catalog page that shows progress, counts errors and can be cancelled | `[x]` |
| G147 | 35 | Catalog records carry level, countries, fields_of_study, funding_type, amount_text, deadline_text, deadline_date (nullable), language_req, apply_url and canonical_key, and every record keeps a `scholarship_sources` row per page (URL, sha256, retrieved_at, provider, trust level, ETag) | `[x]` |
| G148 | 35 | Catalog records are de-duplicated by canonical_key (normalised title + provider domain); a second page fills empty fields and adds a source, a differing value is kept and written down as a conflict, and a verified value is never silently overwritten | `[x]` |
| G149 | 36 | A Discover page over the stored catalog: free-text search plus level, country, field, provider and deadline filters, deterministic ordering (open first, then undated, then closed), each result showing the page's own deadline wording beside the parsed state, and honest empty states - browsing changes nothing | `[x]` |
| G150 | 36 | Eligibility hand-off: from a search result, the deterministic engine runs on that record's verified values against the local profile and shows the same report card as the Eligibility page, and the record can be saved to Saved Opportunities; nothing is ever called eligible | `[x]` |
| G151 | 36 | Search and filters are local-only: no query leaves the device, no record is modified by browsing, and a match is labelled a reading aid rather than a verdict | `[x]` |
| G152 | 37 | A background re-check job: saved records first, then recent catalog records, re-fetched with the guarded fetch (conditional requests, one request per second per host); the page hash decides unchanged vs changed, and a changed page is re-extracted, re-verified against the page text, stored as a new version with the old one kept | `[x]` |
| G153 | 37 | A field-by-field difference is shown in the UI for every changed field: the old value, the new value, and the page text the new value was taken from | `[x]` |
| G154 | 37 | A record is EXPIRED only when its stored, unambiguous deadline_date is earlier than today; an ambiguous or missing date stays "no date" and is never guessed | `[x]` |
| G155 | 37 | A failed re-check says "could not re-check, last verified &lt;date&gt;" and never presents the old copy as fresh | `[x]` |
| G156 | 37 | Deadline reminders: an opt-in Windows notification at 30, 14, 7 and 1 days before a saved record's unambiguous deadline, off by default, never repeated for the same day | `[x]` |
| G157 | 37 | Export: the saved list as CSV and as an ICS calendar file, each carrying the source URL, the deadline text exactly as the page wrote it, and the date the page was last verified | `[x]` |
| G158 | 37 | Warning signs: payment/fee wording on the page, a domain that is neither official nor trusted (exact registrable-domain match, never a substring), a missing source and a missing deadline are shown on the cards and in the why panel; nothing is hidden or deleted, and the wording never calls a page a scam or safe | `[x]` |
| G159 | 37 | Privacy toggles: voice_stt, voice_tts and web_search stay off by default, each feature is gated on its own switch, and the Settings page names the third party and the data for each (the "stay off by default" half was replaced by G171 on 2026-10-22: on by default, with real toggles in Settings) | `[x]` |
| G160 | 38 | The README carries Mermaid diagrams - the student journey, the layered system map, the record pipeline, the re-check decision and the device trust boundary - and every box and arrow describes shipped behaviour | `[x]` |
| G161 | 39 | A visual README: a coloured banner, live badges, and a gallery of fresh screenshots of the shipped pages (Chat, Discover, Saved Opportunities, Eligibility, Catalog, Settings) with captions and a sample-data notice; the grouping of the feature list, the technical content and the honesty rules are unchanged | `[x]` |
| G162 | 39 | The chat quick-action "Explore Countries" opens the Discover page instead of showing a stale "Soon" chip, so no screenshot or shortcut claims a shipped feature is missing | `[x]` |
| G163 | 39 | The Saved Opportunities page holds up with four or more records: the card list scrolls, the saved and checked dates read as dates (not raw ISO timestamps), and the freshness line stays on one line | `[x]` |
| G164 | 39a | A truthful README: the status and milestone table match the code and the tracked docs, the config template is complete, the screenshots are labelled as stub-gateway sample data, and no stale asset or dependency list remains | `[x]` |
| G165 | 40 | Local database encryption at rest (DPAPI or SQLCipher), with a migration for existing databases and an honest note on what the key protects and what it does not | `[ ]` |
| G166 | 40 | OCR and TTS/STT sit behind small Protocol interfaces (like `gateway/`), with the Windows implementation as the default and a fake for tests; no behaviour change | `[ ]` |
| G167 | 41 | GitHub Actions CI on `windows-latest`: Python 3.11, install `.[dev]`, run pytest and the bundle checks that need no build, and show a README status badge | `[ ]` |
| G168 | 42 | UI privacy and status correctness: voice buttons disabled (and linked to Settings) when their switch is off, status text never cut mid-word, copy follows config, accurate tooltips, profile initial, and no clipped panels | `[x]` |
| G169 | 43 | Live catalog run with the real model on 3 portals, at most 8 pages each, with a per-field verbatim audit; every bug found is fixed with a fake-server/fake-gateway regression test | `[ ]` |
| G170 | 44 | A live-proofs checklist in `docs/live_checks.md` for forced-429 failover, neural-voice audibility and clean-Windows packaging; the goals stay open until the owner runs it and reports back | `[ ]` |
| G171 | 45 | Privacy switches are real toggles in Settings, on by default, and saved to `config.toml` from the app; no student edits the file to turn voice or web search on | `[x]` |
| G172 | 46 | One name per page: the top bar names the page, the body no longer repeats it, and the one-line description under the name does not repeat it either | `[x]` |
| G173 | 47 | Every scroll area paints the theme's light page background (view port and content widget), so no page shows black strips in Windows dark mode; My Profile's intro sits in a card; a pixel test guards all pages | `[x]` |
| G174 | 48 | Live voice diagnosis: every Live turn logs event names and numbers only (capture duration, silence-end reason, TTS overlap, engine, confidence) and `tools/voice_probe.py` measures echo with the real mic; nothing is fixed in this phase | `[~]` |
| G175 | 48 | Live voice loop: echo guard (no mic during playback, ~400 ms pause, overlap discard), configurable endpointing with noise calibration and min/max lengths, `voice.language` (en-IN default, en-GB/en-US selectable), a Send now / Edit / Cancel review step with auto-send off, push-to-talk, and a tested Listening/Heard/Thinking/Speaking state machine | `[ ]` |
| G176 | 48 | Live voice engine and noise: STT behind a Protocol (google, whisper_local, fake), faster-whisper CPU int8 with a size-shown explicit download, Silero VAD and noise suppression switches, honest privacy copy, and `tools/stt_bench.py` reporting word error rate | `[ ]` |
| G177 | 49 | Every web address in a chat reply is a real clickable link that opens in the browser, with the text left as plain prose (no markdown) and the spoken reply unaffected | `[x]` |
| G178 | 49 | Government and university domains outside the `.gov`/`.edu` convention (`.go.kr`, `.go.jp`, `.gc.ca`, `.gouv.fr`, `.gob.<cc>`, `.admin.ch`, `.gv.at`, `.govt.nz`) count as official, so a real government portal is never labelled third-party | `[x]` |
| G179 | 49 | While web search is on, the assistant never tells the student it cannot search: it asks for the search, and if the model refuses, the app asks once more in the exact search-request form | `[x]` |
| G180 | 50 | The official-domain rule also accepts the country conventions `edu.<cc>`, `go.<cc>`, `gov.<cc>`, `ac.<cc>` and `nic.in`, still matched exactly on the registrable domain, so lookalikes (`go.kr.fake.com`, `kaist.ac.kr.evil.com`, `fake-edu.np.net`) stay outside | `[x]` |
| G181 | 50 | The chat receives a compact profile summary (degree level, GPA and scale, nationality, preferred countries, funding need, language scores - never the name and never document text) so it stops asking for facts already stored; disclosed in Settings with a switch to turn it off | `[x]` |
| G182 | 50 | The chat checks the local verified catalog first, using the same search as Discover, and cites each record with its source address and last-verified date; web results are marked "unverified lead" | `[x]` |
| G183 | 50 | Level awareness: when the profile says a bachelor's is completed, the chat prefers graduate-level programmes, says why in one line, and says when a result is for another level | `[x]` |
| G184 | 50 | A "Verify this page" button on each official-looking link the chat lists, which runs the existing read-and-verify flow and offers to save the page to the catalog | `[x]` |
| G185 | 51 | Links in a chat reply are a strong, clearly visible blue (not the faded shade Qt paints anchors with), underlined, on both the assistant and the user bubble | `[x]` |
| G186 | 51 | "Verify this page" verifies in the chat itself: the page is read and checked in place, the verified values and the ones the page does not state are shown there, and the record can be saved to the catalog from the reply without opening the Scholarship Pages page | `[x]` |
| G187 | 52 | Crawl discovery prefers scholarship pages: every same-site link is scored by scholarship/funding words (English plus common local-language terms), the highest scores are read first, links are capped per page, depth is capped per run, and obvious non-content (login, cart, news archives, calendars) is skipped | `[x]` |
| G188 | 52 | The crawler reads PDFs published on the official domains it already walks (size-capped), extracts the text layer, and runs the same extract-and-word-for-word verify pipeline, storing the PDF's address and the hash of the PDF bytes | `[x]` |

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

**Where it stands (2026-10-21).** Built: the local profile form for the fields
above, document upload for PDF/text/image with Windows OCR, verbatim-checked
extraction, per-field confirmation and edit-anytime. **Not built:** the
conversational onboarding flow that asks these questions in chat, and a
documented GPA-scale conversion (deliberately deferred - never guessed). G105
therefore stays open; A10's "satisfies" covers the profile + document half
only.

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

**Where it stands (2026-10-21).** Built: SQLite storage, local-by-default
profiles and documents, the three privacy switches, no credentials in source or
in the bundle, and Delete/Clear controls for documents, stored scholarship
records, saved opportunities and the profile. **Not built:** persisted tables
for eligibility evaluations, matches and research runs (they are recomputed,
not stored), and encryption at rest (tracked as G165). G110 stays open for those
two items; A10 and A13's "satisfies" covered the storage and privacy half, not
the encryption.

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
| G207 | M7 | Security review, testing, performance, Windows packaging | Packaged app runs on clean Windows; test suite green; no secrets in bundle | `[~]` |

**Where M7 stands (2026-10-21).** M1-M6 are done and tested. M7 is `[~]`: the
folder build is produced and bundle-audited, but it has not been run on a clean
Windows install, there is no installer, and no separate security/performance
review exists. G207 and G138 are `[~]` for the same reason; G113 (M1-M7) stays
`[~]` until they are done.

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

## Dependencies (resolved 2026-10-21)

- [x] OpenCode gateway — verified live (A8, §19b).
- [x] PySide6 deployment — Qt 6.12 Essentials works; PyInstaller bundled the
      app into `dist\ScholarPathAI` (A25, §19s).
- [x] OCR stack — Windows OCR for images, `pypdf` for text layers (A10, §19d).
- [x] `mcp` SDK — not used. A stdlib MCP client was written instead, so the
      broken external SDK is no longer a dependency (A13, §19g).
- [x] Web research — keyless web search shipped (G136, §19q); the catalog uses
      official portals, not a search API.
- [x] Python for packaging — 3.11, the version the shipped build uses (A25).

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

---

## 19s. A packaged Windows app (G138, G207, 2026-10-21)

- **Owner ask:** build the remaining features, starting with packaging.
- **The build.** `packaging/scholarpath.spec` (PyInstaller, committed) builds
  a folder app: `dist\ScholarPathAI\ScholarPathAI.exe` plus its `_internal`
  runtime. It is a windowed program (no console), and the optional OCR extra
  is bundled only when it is installed. `packaging\build.ps1` does the whole
  thing in one command: install the build tool, build, then audit.
- **The audit** (`packaging\verify_bundle.py`) is part of the build, not a
  nicety: it fails the build when the bundle contains a config, database,
  log, credential file, a private key, or a value that looks like one of the
  service key formats, and it checks that the Python runtime really is
  inside the bundle.
- **Data stays outside.** Config, database and logs live in
  `%APPDATA%\ScholarPath`; the bundle never carries them. `tests/
  test_packaging.py` locks that in: the data folder must not be inside the
  program folder (which is what a frozen app needs), and no user-data or
  secret file may be committed.
- **Measured:** the packaged app opened its own window in **1.6 s** and wrote
  its log to `%APPDATA%\ScholarPath\logs\scholarpath.log`, with the gateway
  connecting normally. The bundle is 198 MB (PySide6 Essentials plus the
  Python runtime).
- **Honest limit:** "runs on clean Windows" was verified on this machine with
  the packaged build; it was not tested on a freshly installed Windows with
  no Python, and there is no installer (no signed `.msi`/Inno Setup yet) -
  the folder build is copied to the target machine as-is.
- **Status (2026-10-21):** G138 and G207 stay `[~]`. The bundle is produced and
  audited; a clean-Windows run and a separate security review are still
  missing. The README and the goal register now say so instead of "done".

---

## 19t. Hardening, honesty and the remaining features (G139-G143, 2026-10-21)

Six changes, each with its own commit and tests.

1. **G143 - fetching is hardened against SSRF.** The host is resolved *before*
   the connection; every resolved address must be public (loopback, private,
   link-local, carrier-grade NAT, multicast, reserved and cloud-metadata
   addresses are refused with the typed `BlockedRequest` error); every
   redirect hop is resolved and checked again; and the address that was
   checked is the address that is connected to, so DNS cannot change the
   answer underneath the request. The only escape hatch is a narrow
   `allow_loopback` flag for the local test server - it never allows a
   private or metadata address.
2. **G139 - verbatim verification is tolerant but still honest.** Both sides
   are normalised first (NFKC, quote and dash styles, words split by a hyphen
   at a line break, spacing), so "5th November 2025" verifies against
   "5 November 2025" and "Chevening's" against "Chevening’s". Dates are
   compared by value, and an ambiguous numeric date (05/11/2025) is not
   guessed. A value that names something ("December 2025") must have every
   word on the page - a year that appears elsewhere cannot carry it.
3. **G140 - privacy switches.** `[privacy]` with `voice_stt`, `voice_tts` and
   `web_search`, all **off by default**. Each feature is gated on its own
   switch, the model is told when search is unavailable (so it never claims
   to have searched), and the Settings page states exactly what each switch
   sends and to whom.
4. **G141 - official pages are an exact allowlist.** A domain counts as
   official-looking when its *registrable* domain ends in `.edu`, `.ac.<cc>`,
   `.gov`, `.gov.<cc>`, `.int` or `.mil`; nothing is matched as a substring
   ("university.edu.example.com" is not official). The student adds their own
   `trusted_domains` in config, matched exactly.
5. **G142 - a Re-check action.** On the Eligibility and Saved pages: every
   record's page is fetched again, the sha256 is compared with the copy that
   was saved, and the card is flagged when the page changed or when the
   stated deadline has passed. A page that cannot be reached says so.
6. **README** - the status banner, the "does not do yet" list and the
   architecture tree now match what the app really does.

## 19u. Catalog of official portals — Phase 1 (G144-G148, 2026-10-21)

Owner roadmap, phase 1 of the discovery plan: the app stops waiting for one
pasted page and walks the official portals itself, storing only what those
pages state. One phase per session; this entry is phase 1 only.

1. **G144 - sources registry.** `src/scholarpath/data/sources_registry.toml`
   ships as the default; `load_registry()` prefers the student's editable copy
   at `%APPDATA%\ScholarPath\sources_registry.toml` and **raises** instead of
   silently substituting when that copy is broken. Entries are validated
   (https only, no duplicate URLs, allowed paths start with `/`). Eight
   portals were verified live on 2026-10-21 and shipped; **CSC**
   (`csc.edu.cn`, HTTP 412) and **Australia Awards**
   (`australiaawards.gov.au`, connection reset / timeout) were dropped rather
   than shipped as a promise the app cannot keep.
2. **G145 - crawler.** `crawler.py` reads `robots.txt` (longest match wins,
   `Allow` wins a tie, wildcards, `Crawl-delay` can only slow a host down),
   collects seeds from sitemap.xml, a sitemap index, RSS/Atom feeds and the
   start page's own same-site links, keeps every *page* inside
   `allowed_path_prefixes` (index files may sit outside), reads HTML only,
   paces one request per second per host, sends `If-None-Match` /
   `If-Modified-Since` and reports `304` as unchanged, caps pages per portal,
   and refuses to connect to a private address.
3. **G146 - the run.** `catalog.py` (no Qt, so it is testable headless) does
   crawl → extract → verify → save, counts created / updated / merged / errors
   and stops between pages when asked. `ui/catalog_page.py` wraps it in a
   `QThreadPool` job with a progress bar, a per-portal list with switches, a
   pages-per-portal limit, an error box and a Cancel button.
4. **G147 - the record.** The `scholarship` table gained the catalog columns
   (old databases are migrated in place) and `scholarship_sources` keeps every
   page behind a record with its sha256, retrieval time, provider, trust level
   and ETag. `deadline_date` is parsed only from unambiguous page wording and
   stays `NULL` otherwise.
5. **G148 - one record, many pages.** `canonical_key` = provider domain +
   normalised title words; the same page twice adds no second source; an empty
   field is filled by a later page; a differing verified value is **kept** and
   the difference is stored under `data["conflicts"]` with the page that said
   it.

## 19v. Discover: search, filters and the profile hand-off — Phase 2 (G149-G151, 2026-10-21)

Phase 2 of the discovery roadmap. The catalog from phase 1 fills the database;
this phase is how a student actually finds something in it, without the app
ever pretending to judge them.

1. **G149 - Discover page.** Search covers the words a page actually states
   (title, provider, country, level, fields of study, funding, amount, deadline
   wording, language requirement), folded for case, accents, quote and dash
   style. Filters: level (bachelor / master / PhD, matched from the page's own
   wording as whole words), country, field of study, provider (only portals that
   actually have records) and deadline state (still open / closing within 90
   days / already closed / no readable date). Ordering is fixed and explainable:
   open deadlines first (closest first), then records without a readable date,
   then closed ones. Each card shows the page's own deadline sentence next to
   the parsed state, so a mis-parse is visible rather than hidden.
2. **G150 - the hand-off.** "Check against my profile" runs
   `eligibility.evaluate` on the record's stored, verbatim-verified values and
   shows the same `ReportCard` the Eligibility page uses, inside a dialog. The
   save toggle writes to Saved Opportunities; the dialog says so when the
   profile is empty (every requirement would read unknown).
3. **G151 - local only.** The search is a loop over rows already in SQLite. No
   query, filter or result leaves the machine, and browsing never writes to a
   record - asserted by a test that compares the stored row before and after a
   search and a reload.
4. **Wording.** The page lead says "a match is not a verdict", the result count
   says "N of M record(s) match", and the dialog repeats that nothing is a
   probability and every requirement must be confirmed on the official page.

## 19w. Freshness and safety — Phase 3 (G152-G159, 2026-10-21)

Phase 3 of the discovery roadmap, specified by the owner on 2026-10-21. The
catalog is only worth anything if it stays true, and a student must be able to
see the warning signs without being told what to think.

1. **G152 - the re-check job.** A background job re-fetches records: the saved
   ones first, then the most recent catalog records. It reuses the guarded
   fetch (public addresses only, conditional requests with the stored ETag /
   Last-Modified, one request per second per host). The stored sha256 decides
   the outcome: the same hash means unchanged; a different hash means the page
   changed, so the page is re-extracted with the model, every proposed value is
   re-verified word-for-word against the new page text, the new version is
   stored and the previous version is kept.
2. **G153 - the difference.** For a changed page the UI shows every field that
   differs: the old value, the new value and the sentence of the new page the
   new value was taken from. Nothing is updated behind the student's back
   without a visible difference.
3. **G154 - expiry.** A record is EXPIRED only when its stored `deadline_date`
   is a single unambiguous day that lies before today. A date the page words
   ambiguously stays "no date" - it is never guessed into a day.
4. **G155 - a failed check says so.** When the page cannot be fetched, the
   record reads "could not re-check, last verified &lt;date&gt;". The old copy is
   never presented as fresh.
5. **G156 - reminders.** A Windows notification at 30, 14, 7 and 1 days before a
   saved record's unambiguous deadline. Opt-in (`[reminders] enabled`), off by
   default, and never repeated for the same record on the same day. Records
   without a readable deadline are never reminded about.
6. **G157 - export.** The saved list exports as CSV and as an ICS calendar
   file. Both carry the source URL, the deadline text exactly as the page wrote
   it, and the date the page was last verified. Only records with a readable
   deadline become calendar events.
7. **G158 - warning signs.** Four signs are looked for: payment or fee wording
   on the page, a domain that is neither official nor trusted, a missing source
   and a missing deadline. A domain is official when its registrable domain
   matches exactly - `.edu`, `.ac.xx`, `.gov`, `.gov.xx` - or the student's own
   `trusted_domains`; a lookalike such as `harvard.edu.fake.com` or
   `chevening-scholarships.org` is not official. Signs appear on the cards and
   in the why panel. A record is never hidden or deleted, and the wording says
   "warning sign" - never "scam", never "safe".
8. **G159 - privacy switches.** `voice_stt`, `voice_tts` and `web_search` stay
   off by default, each feature is gated on its own switch, and the Settings
   page states which third party receives which data when a switch is on. The
   deadline reminder is a local Windows notification and sends nothing.

## 19x. README diagrams (G160, 2026-10-21)

The owner asked for a flowchart or architecture diagram in the README so the
system can be understood at a glance. Requirement G160: the diagrams are
Mermaid text in `README.md` (no image build step, editable), and no box or
arrow may describe something the code does not do. Five diagrams:

1. **The student journey** - open, fill the profile, run the catalog, Discover,
   check against the profile, save, then re-check / remind / export.
2. **The system map** - four layers plus the model seam: Qt UI, domain logic
   (no Qt), local SQLite, the guarded fetch, the gateway, the portals. The
   gateway is the only provider-aware code; `sources.py` is the only door to
   the web.
3. **How a scholarship record travels** - registry, crawler, guarded fetch,
   propose/verify/merge, catalog, then Discover / save / re-check / export /
   reminders, with a numbered list beside the diagram because a summary
   diagram cannot carry every rule.
4. **The re-check decision** - 304 or same sha256 = unchanged; a different
   hash = re-extract and verify; unreachable = "could not re-check, last
   verified &lt;date&gt;"; EXPIRED only from a stored `deadline_date`.
5. **What crosses the device boundary** - the local box, the model service the
   student configures, and the three off-by-default third parties
   (Google speech, Microsoft speech, DuckDuckGo).

Verification: all five blocks parse with `mermaid.parse` (Mermaid 12.2) and
were rendered to PNG with `@mermaid-js/mermaid-cli` 12.0 against the system
Edge before commit; the rendered images were inspected for misleading edges,
hyphen-split words and text that only fits at an unreasonable width. No code
changed, so the suite is still green: 558 tests.

Limits: the diagrams are hand-maintained. A new page or module does not appear
in the map until someone edits the Mermaid block; the file tree under
"Architecture" stays the authoritative inventory.

## 19y. A visual README, real screenshots, and the two things they exposed (G161-G163, 2026-10-21)

The owner asked for more feature screenshots in the repository and a README that
is colourful and inviting rather than a flat wall of text. Requirement G161: a
banner, live badges, a gallery of fresh screenshots of the shipped pages, and
the technical content plus the honesty rules unchanged.

What shipped:

1. **`docs/banner.svg`** - a self-contained banner (gradient, mortarboard mark,
   tagline, no external fonts, no scripts), hand-written SVG so it stays sharp
   at any width and needs no build step.
2. **Eight screenshots** - seven page captures in `docs/screens/` (Discover,
   Saved Opportunities with the difference panel open, Eligibility, Catalog,
   Settings and My Profile, plus the Saved page) and `docs/screenshot.png` as
   the hero chat capture. They are real `MainWindow` grabs rendered offscreen
   (`QT_QPA_PLATFORM=offscreen`, plus `QT_QPA_FONTDIR` so the Windows fonts
   load) from the shipped build, seeded with sample records in a throwaway
   `SCHOLARPATH_HOME`; the real profile and database are never touched. The
   harness uses a stub gateway named like a live one, so the green "Live" pill
   is illustrative; G164 now says so in the README.
3. **README structure** - banner, tagline, seven badges (the status badge now
   reads "phase 3 shipped"), nav links, the screenshot gallery with captions
   and a sample-data notice, GitHub alert callouts, and the 30-bullet feature
   list grouped under Chat / Profile / Find and verify / Keep every record true
   / Voice / Under the hood. The full config, the file map and the long
   command list moved into `<details>`; the misplaced privacy bullet moved out
   of the limits list into Privacy, where it belongs. Every diagram, table,
   command and limit of the previous README is retained.
4. **G162 - the stale "Soon" chip.** The "Explore Countries" quick action
   still said "coming in Milestone 6" although Discover shipped in phase 2. It
   now opens Discover, and the four quick actions are a balanced 2 x 2 grid
   instead of a 3 + 1 flow.
5. **G163 - the Saved page with four or more records.** Its card list had no
   scroll area, so the cards were squeezed and clipped; it now lives in a
   `QScrollArea` and returns to the top on reload. The saved, checked and
   retrieved dates read as dates (`2026-10-20`) instead of raw ISO timestamps,
   and the freshness line no longer wraps into three words per line.

Why G162 and G163 are in this task: both were found by rendering the
screenshots. A screenshot that shows a "Soon" chip on a shipped feature, or a
saved list that clips its own cards, would misrepresent the build.

Verification: **562 tests pass** (`pytest`, exit 0), including four new ones -
the Saved list is a scroll area, the saved date is a date, "Explore Countries"
opens Discover, and no quick action carries a "Soon" badge. The five Mermaid
blocks still parse with `mermaid.parse` (Mermaid 12.2). Every screenshot was
inspected at full size, and the banner was rendered in the system Edge to
confirm the browser output (the SVG uses no web font).

Limits: the screenshots show fictional providers on reserved `.example`
domains, which the README states; they are regenerated by a throwaway script in
the temp folder, not by a tool in the repository, so a future UI change means
re-taking them by hand. The banner and the gallery are maintained like the
diagrams.

---

## 39a. Truth pass: M7, Phase 4 and the docs (G164, G207, 2026-10-21)

The audit found three documents disagreeing with each other and with the code:
`goals.md` marked M7 done, `achievements.md` listed M7 as not achieved, and the
README said "all seven milestones are complete". It also found stale dependency
items, a "Full config template" that was not full, screenshots whose green
"Live" pill came from a stub gateway, and Phase 4 with no requirement rows.

What changed (docs only - no application code):

1. **M7 is `[~]`, not done.** G207, G138 and G113 now say: the folder build is
   produced and bundle-audited; a clean-Windows install, an installer and a
   separate security/performance review are still missing. README status and
   the milestone table say the same. The truth is in one place, not three.
2. **G105 and G110 reconciled.** Both stay open with the exact remainder
   written down: conversational onboarding for G105; stored
   eligibility/match/research-run tables and encryption for G110. A10/A13's
   "satisfies" covered only the built half.
3. **G107 note.** Funding-type ranking is deliberately deferred; funding stays
   descriptive.
4. **Dependencies resolved.** The "to verify (open)" list is now a resolved
   list; Python 3.11 is the packaging target and PyInstaller bundling is
   proven.
5. **Phase 4 and the next steps have rows.** G164 (this README truth pass, now
   `[x]`), G165 (DB encryption), G166 (OCR/TTS interfaces), G167 (GitHub
   Actions), G168 (UI privacy/status), G169 (live catalog run), G170 (live
   proofs checklist).
6. **README.** "All seven milestones complete" and M7 "Done" replaced with
   "M1-M6 + phases 1-3 done; M7 packaged, clean-Windows pending". The config
   block now lists every key (`models`, `fallback_providers`,
   `failover_attempts`, `api_keys`, `api_model`, `api_models`, `account_keys`,
   `[mcp]`) and `config.example.toml` gained the missing keys. Screenshots are
   labelled as a stub gateway with a sample profile and sample records. The
   unused `docs/screens/chat.png` was removed.
7. **Packaging copy.** "So the app starts on a clean Windows" in the README was
   an untested claim; it now says the runtime is bundled and the clean-Windows
   run is still to be done.

Verification: **562 tests pass** (docs-only change), and the README's claims
were checked against `goals.md`, `achievements.md` and the code paths named in
the audit.

---

## 40. Local encryption and OCR/TTS interfaces (G165, G166)

- **G165 (DB encryption).** Encrypt the local SQLite database at rest with
  DPAPI (per Windows user) or SQLCipher, migrate existing databases in place,
  and document what the key protects (a copied database file) and what it does
  not (a compromised logged-in session, screenshots, exports). A restore path
  and a key-loss message are part of the design.
- **G166 (interfaces).** Move OCR and TTS/STT behind small `Protocol`
  interfaces, mirroring `gateway/`: Windows OCR / Edge+SAPI as the default
  implementations, a fake for tests. No behaviour change; tests keep passing.

## 41. CI (G167)

A GitHub Actions workflow on `windows-latest` with Python 3.11: install
`.[dev]`, run `pytest` (no network, no model), and run the parts of
`packaging/verify_bundle.py` that do not need a built bundle. Add the workflow
badge to the README. The suite must never depend on a live provider.

## 42. UI privacy and status polish (G168)

- Mic and Live voice disabled and greyed when `privacy.voice_stt` /
  `voice_tts` are off; the tooltip says "Off. Turn on in Settings > Privacy"
  and a click opens Settings at that section.
- The status strip elides with the full text in a tooltip (or wraps to two
  lines); never cut mid-word. The config path keeps a tooltip only.
- The hint, subtitle and "What works today" follow the config: web search and
  voice read "Off (enable in Settings)" when their switch is false.
- The stale "search is not built yet" tooltip and the "Official pages you
  paste" subtitle are corrected; the dead `_not_available` path is removed.
- The header avatar shows the first letter of the profile name (generic icon
  when no name).
- The right profile panel's 23 px clip is fixed; My Profile is wrapped in a
  scroll area so the Save row never clips at any Windows scaling.

**Where it stands (2026-10-21).** Built in A32. `PrivacyGate` disables the
real mic and Live voice controls while the switch is off (the mic paints muted,
Live voice has a `:disabled` style), keeps the exact tooltip, and sends a click
or Enter/Space to Settings with the privacy card scrolled into view. The status
strip uses word-aware elision with the full sentence in its tooltip; the config
path is a short "Config" label whose tooltip holds the path. The chat subtitle,
hint, status line and the "What works today" tags read the `[privacy]` values,
so web search and voice say "Off (enable in Settings)" until turned on.
"Find Scholarships" opens Discover and focuses its search, the old
`_not_available` path is gone, and the avatar is the profile's first letter
(person glyph when empty). At 1120x720 the right panel needs no scrollbar; My
Profile is a `QScrollArea`. 573 tests pass, including 11 new UI tests.

## 43. Live catalog verification (G169)

Use a temporary `SCHOLARPATH_HOME` so the real data is untouched. Run the
headless catalog with the real model on Chevening, DAAD and Erasmus+ only,
at most 8 pages each, respecting robots.txt and one request per second. Record
pages fetched/skipped, created/updated/merged, conflicts, errors and time.
Print a per-record table: title, domain, source URL, and each field with
"verbatim on page: yes/no". Then check: no field absent from its page, no
non-scholarship page saved, no wrong merge or missed duplicate, no
`deadline_text` without a justified `deadline_date`, no truncated
`apply_url`, and no unhandled timeout/bad JSON/rate limit. Run the freshness
re-check (unchanged pages must report unchanged) and `scam_flags` (official
portals must get no false warning), and render Catalog + Discover offscreen
with this data (search "daad" and "master"; filters must not leak). Fix each
bug with a fake-server/fake-gateway regression test; ask before any design
decision. Record the run honestly in `achievements.md`.

## 44. Live proofs checklist (G170)

`docs/live_checks.md` with exact manual steps, inputs and a pass/fail box for:
forced-429 provider failover (G127-G129), neural-voice audibility (G133), and
the packaged app on a clean Windows VM (M7). `fallback_providers` and
`account_keys` are documented in `config.example.toml`; the checklist tells the
owner how to use them. These goals stay `[ ]` / `[~]` until the owner runs the
checklist and reports back; the file is a procedure, not evidence.

## 45. Editable privacy settings (G171)

The Settings page showed the privacy switches as read-only lines and told the
student to edit `config.toml` by hand. That assumes every student is a
programmer. Change it:

- The three privacy switches (voice input, spoken replies, web search) are
  real toggles on the Settings page. Turning one changes the running app
  immediately and writes the value to the local `config.toml`.
- They are **on by default** so voice and web search work out of the box. The
  page still states, next to each switch, exactly what leaves the device and
  to which third party; turning one off is one click.
- The write is atomic and preserves the rest of the file, including comments
  and the user's gateway keys. A failed write is shown on the page and the
  toggle returns to its previous value; it never pretends to have saved.
- Tests cover the default values, the save/round-trip, a failed write, and the
  toggles changing the main window's gates and search behaviour.

**Where it stands (2026-10-22).** Built in A33. `SettingsPage` draws a
`PrivacySwitchRow` per switch: the feature name, the disclosure (what leaves
the device and to whom), an On/Off state and a painted `ToggleSwitch` (Space
and Return work, it is keyboard reachable). Flipping one writes the file
through `config.save_privacy_config`, which changes only the three privacy
values, keeps every comment and every other section, validates the result and
replaces the file atomically; a failed write is reported on the page and the
toggle returns to its old value. `MainWindow` listens to `privacy_changed`, so
the mic gate, the Live voice gate, the "What works today" tags, the status
line and `ChatController.search_enabled` follow the switch at once. The
defaults are on (`PrivacyConfig`), `config.example.toml` matches, and no
user-facing text tells a student to edit a config key any more. An existing
`config.toml` keeps its own values until a toggle is flipped. 579 tests pass,
including 6 new ones.

## 46. One name per page (G172)

The window's top bar has always named the page ("Settings", "Discover", ...)
and every page also drew its own big heading with the same word, so the name
appeared twice on every page. The shell header is the single name:

- The eight page bodies (Profile, Documents, Scholarship pages, Eligibility,
  Catalog, Discover, Saved, Settings) lose their duplicated `PageTitle2`
  heading and keep their lead sentence, which says what the page is for.
- The top bar keeps the page name and gains a one-line description of that
  page. The description no longer repeats the name, and the Catalog and
  Discover pages get their own line instead of the chat one they used to
  show.
- The top-bar title block takes the spare width, so the description is one
  line instead of wrapping after a few words.
- The status strip gets matching lines for Catalog and Discover instead of
  the chat line.
- The README gallery is re-captured from the real window, so every screenshot
  shows the shipped page.

## 47. Scroll areas paint the page colour (G173)

Every page shows black strips around its cards when Windows runs in dark
mode: the text on the My Profile page sat on black, and the Saved page's list
body was black from top to bottom. The culprit is not the cards. A
`QScrollArea` is made of plain `QWidget`s: the viewport Qt creates inside it
and the widget set with `setWidget`. None of them had a background in
`theme.py`, so Qt fell back to the system window colour, which is near-black
under the dark palette. The named rules (`DocScroll`/`DocBody`,
`RightScroll`/`RightBody`, `ProfileScroll`, `Transcript`) only covered the
scroll area itself, and only for some pages.

The fix is one block in `ui/theme.py`, so every page, the right-hand panel,
the chat transcript and the eligibility dialog get it at once:

- `QScrollArea` (the frame) is the page colour with no border;
- `QScrollArea > QWidget#qt_scrollarea_viewport` is the page colour;
- `QScrollArea > QWidget > QWidget` (the content widget) is the page colour.

There are no per-page styles. On My Profile the intro sentence moved into a
`PanelCard` of its own (`profile_page.py`), so it reads as a note above the
form instead of loose text. The page, the viewport and the content widget all
paint `#FBFCFE` now; the cards stay white.

`tests/test_ui_page_backgrounds.py` guards the result: it builds the real
window off-screen (`WA_DontShowOnScreen`), selects each of the nine pages,
grabs it, samples every fourth pixel, and fails when more than 1% of the
samples are near-black (every RGB channel below 48). The failure message
names the darkest 80px blocks. With the fix the densest page (Settings) is
0.26% dark, which is text; without it the test fails on Profile (6.8%) and
Saved, exactly the pages that looked broken. The README gallery was
re-captured, so the profile and saved screenshots no longer show the strips.

Known limit: the native combo-box arrow still paints as a small grey block
under the Windows dark palette. It is a glyph, not a background, and is left
for a separate style pass.

## 48. Live voice accuracy (G174-G176)

Dictation in the composer already works and must not change: one click, one
clip, the words land in the composer for review. This work is about **Live
voice mode**, where the app listens, sends, speaks the reply and listens
again with no clicks. The constraints for every phase:

- **Privacy stays honest.** The Google clip and the Microsoft reply text are
  each disclosed and each behind its own opt-in switch; nothing recorded is
  stored, and the probe prints the words only to the owner's console, never
  to the log.
- **No network in tests.** Tests use a fake microphone, fake audio and a fake
  recogniser. The probe is the only piece that touches the real microphone
  and the real services, and it says so.
- **Measure first.** Phase 1 adds instrumentation and a probe; it fixes
  nothing. Phase 2 changes the loop, Phase 3 changes the engine. One commit
  per phase.

**Phase 1 (G174).** Each Live turn logs a small set of `voice event=...`
lines with numbers only - no audio, no transcript text: capture start (engine,
language, max seconds, whether TTS was already playing), capture end (wall
duration, clip duration, how the wait ended: silence, phrase limit, start
timeout, stopped, error), transcription (engine, characters, confidence when
Google sends one, elapsed) and the speech/listen boundary in the window.
`tools/voice_probe.py` replays one cycle with the real mic: it records the
student, speaks a canned reply, records the reply-playback window and the
window right after playback, then prints the heard text, the durations and how
much of the reply the microphone heard (word overlap). The phase report says
whether the evidence points at echo, an early cut-off, room noise or engine
accuracy. No thresholds, guards or settings change in this phase.

### Phase 1 findings (2026-10-22, this machine)

Measured with `tools/voice_probe.py --skip-student` on the owner's laptop
(mic and speakers both present, Edge neural voice playing 6.91 s of audio in
7.1-7.4 s). Numbers, not impressions:

| Measurement | Result |
| ----------- | ------ |
| Room noise, 2 s raw | peak 1-891, RMS 0-76 (of 32767) - a quiet room |
| Mic level while the reply played, raw | peak 509-3149, RMS 40-257 - the microphone **does** hear the speaker, but faintly (-36 to -20 dBFS) |
| Mic level in the 3 s after the reply | peak 2-620, RMS 0-71 - back to the noise floor, **no audible tail** |
| Transcript of the playback window | "nothing intelligible" for both `en-IN` and `en-US` - the reply is too quiet for the service, so no echo words came back |
| The app's own capture, 0.000 s after playback ended | wait 1.44-6.59 s, **clip 1.44-3.60 s**, ended with reason `silence` |
| Ambient threshold the library chose | 193, while room noise peaks reached 891 - **4.6x the threshold** |
| Confidence from the engine | never sent (the free Google endpoint omits it; the library's `with_confidence=True` would have invented 0.5, so this build reports "not sent" instead) |
| Language tag | `en-IN` and `en-US` are both accepted (no request error), so the tag is not the problem |

What the evidence says:

1. **Early cut-off is real, and it is the loudest problem.** The capture ends
   after 1.4-3.6 s with reason `silence` - the library stops at the first
   0.8 s pause, and the ambient threshold (193) sits far below the room's
   noise peaks (891), so a noise transient opens the "speech" window and the
   next pause closes it. In the first run the clip was cut 0.53 s **into**
   the reply, after 2.1 s of silence had already been swallowed as speech.
   A real utterance loses its first and last words the same way.
2. **Echo is a mechanism, not yet a symptom here.** The microphone picks up
   the reply (peak 891 -> 3149, RMS 76 -> 257) but the level is too low for
   the recogniser to turn it into words, and the room is dead quiet
   afterwards (peak back to 2). On this machine, at this volume, the reply is
   not heard as speech. The risk is real though: the loop opens the
   microphone **0.000 s** after playback ends, with no pause at all, so any
   room with a tail - or a louder system volume - would capture the reply.
3. **Room noise is not the complaint.** The floor is 0-76 RMS. The noise
   problem is that the threshold is set *from* that floor and is too close to
   the peaks.
4. **Engine accuracy could not be judged in this run** - nobody spoke, so the
   only speech available was the app's own reply at -36 dBFS. The owner has
   to run the probe's first step (`tools\voice_probe.py`, without
   `--skip-student`) and say a sentence; that measures what the engine does
   with a real Indian-English voice and gives the accuracy number the phase
   report needs.

Not changed in this phase, on purpose: no threshold, no pause, no language
setting, no review step, no state machine, no new engine. Those are Phase 2
and Phase 3.

Phase 1 is done except for one command the owner has to run, because it needs
a human voice: `.venv\Scripts\python.exe tools\voice_probe.py` (without
`--skip-student`) and say the sentence it prints. That fills in the
engine-accuracy row above.

## 49. Search answers: clickable links, honest labels, no false refusals (G177-G179)

The owner asked three things after a live answer about Korean scholarships:

1. the web addresses in a reply must be **clickable links**, not plain text;
2. the app kept saying it "can't search" / "can't confirm";
3. were results **barred** because the site was not an official `.edu`/`.gov`
   domain?

**What the code actually does (checked, not guessed).**

- Nothing is barred. `websearch.search` returns every result it parses (cap 6,
  duplicates dropped). Official-looking domains are **ranked first**; every
   result is **labelled** for the model: "official-looking domain", "a domain
   you marked as trusted" or "not an official domain".
- The label was **wrong** for the Korean government portal. `official.py` knew
  only `.edu`, `.ac.<cc>`, `.gov`, `.gov.<cc>`, `.int`, `.mil` and `europa.eu`.
  Korea's government uses `.go.kr`, so `www.studyinkorea.go.kr` - the portal
  run by the Korean government - was labelled third-party, and the model
  repeated that label as "I can't confirm that".
  Live check (this machine, 2026-10-22, query "study in korea scholarship
  undergraduate 2027"): all 6 results came back labelled third-party, twice
  for `www.studyinkorea.go.kr`.
- The app **does** search. The log shows the searches running (6 results each,
  at 11:34, 11:35, 11:37 and 12:09). The "I can't search" wording came from
  the model, which sometimes answers "I can't browse the web" instead of
  sending the search request, and from the "not an official domain" label
  spread over every result.
- Links were plain text by design: the model is told to write plain prose
  with no markdown, and the assistant bubble is a `QLabel` with plain text and
  mouse selection only. Nothing turned a bare URL into a link.

**What must be true after this section.**

- **G177 - clickable links.** Every `http(s)` address in a chat reply is
  rendered as a link that opens in the browser. The reply stays plain prose
  (no markdown, no asterisks), the URL text stays visible, and the spoken
  reply is unchanged (links are spoken as "link in the chat").
- **G178 - honest official labels.** The official-domain rule covers the
  government and university conventions used outside the US: `.go.kr`,
  `.go.jp`, `.gc.ca`, `.gouv.fr`, `.gob.<cc>`, `.admin.ch`, `.gv.at`,
  `.govt.nz`, next to the ones it already knew. Matching stays exact on the
  registrable domain - a lookalike such as `studyinkorea.go.kr.example.com`
  is still not official. The student's own `trusted_domains` still count.
- **G179 - no false refusals.** While web search is on, the assistant never
  says it cannot search: it asks the app for the search. If the model answers
  with a "I can't browse the web" refusal, the app asks once more in the
  exact search-request form and, if the model complies, the search runs. One
  retry only, and the retry is logged.

**Out of scope.** The search service itself (still the keyless DuckDuckGo
lite endpoint), the six-result cap, the ranking, the privacy switch, and the
"confirm on the official page" advice - that advice stays, because a
third-party page is still not proof.

**Done (2026-10-22).** 610 tests pass. The links in a reply are anchors that
open in the browser (the reply stays plain prose, the spoken reply is
unchanged); the government conventions are in the one rule that decides what
is official, with the lookalike guard still exact; and a model that refuses
to search is asked once more in the exact form the app reads. Verified live:
the same Korea query that returned six third-party results now returns the
Korean government portal first, marked official, with the blogs behind it.


## 50. Chat context: the profile, the catalog, the level, the verify button (G180-G184)

The owner asked for five things in one pass, all about the chat using what the
app already has instead of asking the student again:

1. **Domain gaps.** The official rule missed the conventions other countries
   use for their own ministries and universities: `edu.np`, `edu.au`, `edu.cn`,
   `edu.sg`, `edu.my`, `edu.in` were already covered by the generic `edu.<cc>`
   second level, but `go.<cc>` was only known for Korea, Japan and Indonesia,
   and `nic.in` (India's National Informatics Centre) was unknown. The rule
   now accepts `edu.<cc>`, `go.<cc>`, `gov.<cc>`, `ac.<cc>` and `nic.in`
   generically. It is still matched **exactly on the registrable domain**, so
   `go.kr.fake.com`, `kaist.ac.kr.evil.com` and `fake-edu.np.net` stay outside.
   The registry's own portals and the student's `trusted_domains` keep working.
2. **Profile summary.** The chat is given a compact summary of the saved
   profile - degree level, GPA and scale, nationality, preferred countries,
   funding need, language scores - so it never asks for a fact that is already
   stored. The name and the documents are **never** included. It is sent with
   the chat message to the model service, so Settings discloses it and a switch
   (`privacy.chat_profile`) turns it off; off means the model gets nothing.
3. **Catalog first.** On every turn the chat searches the local verified
   catalog with the same search Discover uses (`search_records`, one content
   word at a time so a whole sentence still finds a record). Matching records
   go to the model **before** any web results, each with its source address and
   last-verified date. Web results are labelled **unverified lead**.
4. **Level awareness.** When the profile says a bachelor's degree is completed,
   the model is told to prefer graduate-level programmes, say why in one line,
   and say when a record or result is for another level. A catalog record whose
   page states only bachelor's study is flagged as such in the catalog block.
5. **Verify this page.** Every official-looking link in a reply gets a
   "Verify this page" button. It opens the Scholarship Pages page with that
   address and runs the existing read-and-verify flow (fetch, propose, verbatim
   check, Save), so the student can put the page into the catalog without
   pasting it again.

Honesty rules that stay: nothing is called verified unless the page said it;
the catalog block says which records were verified and when; web results are
never called verified; the profile summary is exactly the listed fields.

**Done (2026-10-22).** 642 tests passed. One commit per item: `e2ff477`
(G180), `4273866` (G181), `650ab77` (G182), `d798371` (G183), `fe68bfb`
(G184).


## 51. The links read, and the verify button stays in the chat (G185-G186)

The owner read a reply and reported two things about the chat bubble:

1. **The link is faded.** Qt does not honour the `QLabel#AsstBody a` rule for
   anchors inside a rich-text label - the address is painted with the palette's
   link colour, which reads washed out on the light-blue bubble. The colour has
   to travel **with the anchor itself**, as an inline style, and it must be a
   strong blue that is legible on white, on the pale-blue assistant bubble and
   on the orange user bubble.
2. **The verify button left the chat.** It used to switch to Scholarship Pages
   and start the flow there, so the student lost the conversation to answer a
   question the conversation had just raised. It must verify **in place**: read
   the page, check every value against it, show what the page states and what
   it does not, and offer to save the record to the catalog, all inside the
   reply. Nothing is saved without the student pressing Save.

Honesty rules that stay: the panel says how many proposed values appear
word-for-word on the page and names the ones that do not; a fetch failure or a
model failure is stated plainly and nothing is invented; the save keeps the
source URL, the retrieval time and the page hash, exactly like the Scholarship
Pages page.

**Done (2026-10-22).** See `achievements.md` A43-A44.




## 52. Crawler breadth without loosening verification (G187-G188)

STEP 1 of the owner's four-step crawler plan. The rules that do **not** change:
official pages only, word-for-word verification, source address + page hash
stored, robots.txt obeyed, one request per second per host, no network in tests.

1. **Scored discovery.** Links are ranked by scholarship/funding words - the
   task's list (scholarship, fellowship, grant, funding, bursary, apply,
   eligibility, deadline) plus common local-language terms (Nepali, Korean,
   Japanese, Chinese, Indonesian/Malay, Vietnamese, Thai, German, French,
   Spanish, Portuguese, Polish, Russian, Arabic). The highest scores are read
   first, a page contributes at most a fixed number of links, and depth is
   capped even when the registry asks for more.
2. **Skip obvious non-content.** Login, sign-up, account, cart, checkout,
   calendar, archive, tag, author and search-result paths are never queued.
3. **PDF support.** A PDF inside the allowed paths of an official portal is
   fetched (size cap), its text layer extracted, and the same extract -> verify
   -> save pipeline runs on it. A scan with no text layer is refused and said
   so; nothing is invented. The source address and the hash of the PDF bytes
   are stored, and the record says it was read from a document.
4. **Page cap per run.** The whole run stops at a fixed page total, so eight
   portals cannot each spend the full per-portal allowance.

Steps 2-4 of the plan (candidate finder, JS rendering, signed catalog
snapshot) are **not** part of this one.

**No new external dataset or service is used in STEP 1**: PDFs and links come
from the portals already in the sources registry, so no third-party terms
change what this step may do.

**Done (2026-10-22).** 682 tests passed, no network. Commits: `ae24260`
(requirement rows), then the code and tests, then this docs update. See
`achievements.md` A45 (G187) and A46 (G188). Files: `discovery.py`
(`score_link`, `is_noise`, `SCHOLARSHIP_TERMS`, `page_links(allow_pdf=...)`),
`crawler.py` (`ranked_links`, priority queue, depth/link caps, PDF branch),
`sources.py` (`pdf_from_resource`, `MAX_PDF_BYTES`), `catalog.py`
(`MAX_PAGES_PER_RUN`), `ui/catalog_page.py` (page copy), tests
`test_crawler_discovery.py`, `test_crawler.py`, `test_catalog.py`.

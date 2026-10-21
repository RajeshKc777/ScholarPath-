<div align="center">

# ScholarPath AI

**Find scholarships you can actually get — with sources you can actually check.**

A local-first desktop assistant that matches students to legitimate scholarship
opportunities and explains, requirement by requirement, why they do or do not fit.

<br>

![Status](https://img.shields.io/badge/status-catalog%20phase%201-4f8cff?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/Qt-6.12-41CD52?style=flat-square&logo=qt&logoColor=white)
![Tests](https://img.shields.io/badge/tests-488%20passing-2ea043?style=flat-square)
![License](https://img.shields.io/badge/license-view--only%20%C2%B7%20all%20rights%20reserved-b3261e?style=flat-square)

</div>

<br>

<div align="center">
  <img src="docs/screenshot.png" alt="ScholarPath AI desktop window showing the Reddit-orange dashboard" width="880">
  <br>
  <sub><em>Scholarship pages verified against the page itself, live chat, web search, voice input and a spoken reply — no invented fields, no silent data sharing.</em></sub>
</div>

---

## Why this exists

Scholarship advice online is mostly guesses: unverified deadlines, invented
funding amounts, "you're eligible!" with no source behind it. ScholarPath AI is
built on the opposite rule set.

| Principle | What it means in practice |
| --------- | ------------------------- |
| **Official sources only** | Universities, government portals, and programme administrators are the authority — not search snippets. |
| **Explainable eligibility** | Every requirement is reported as satisfied, unmet, unknown, or needs manual verification. Never a bare "you qualify". |
| **No fabrication** | If a fact cannot be verified, the app says so. It does not invent deadlines, amounts, or criteria. |
| **Local-first** | Profiles and academic documents stay on your machine. Nothing leaves the device by default. |
| **Honest failure** | A broken provider produces an error, never a plausible-looking answer. |

---

## Status

> **All seven milestones are complete**, and **phases 1 and 2 of the discovery
> roadmap** are in: the app now walks **official scholarship portals** itself
> and lets you **search what they stated**. Chat runs **live through the local
> OpenCode service**, profiles/documents work locally, and you can **verify a
> scholarship page**: paste the official URL, and only values that literally
> appear in the page text are offered - every saved record carries its source
> URL, retrieval time and page hash. The **Catalog** page reads a registry of
> official portals (sitemaps, feeds, same-site links, robots.txt, one request
> per second per host) and stores what those pages state, merged into one
> record per scholarship; the new **Discover** page searches and filters those
> records and hands one to the same deterministic eligibility checks. The chat
> can also **search the web** for you (off by default), point it at a site's
> scholarships page to list that page's own links, and **re-check** saved
> records to see whether a page changed or a deadline has passed. Voice input
> and a spoken reply are available too — both **off by default**, because they
> send data to a third party. There is a packaged Windows build
> (`packaging\build.ps1`).

| # | Milestone | Status |
| - | --------- | :----: |
| M1 | Repository, config, desktop shell, chat loop | **Done** |
| M2 | OpenCode gateway adapter, model registry, task routing | **Done** |
| M3 | Profiles, document ingestion, OCR, confirmed extraction | **Done** |
| M4 | Source discovery, official-source verification, storage | **Done** |
| M5 | Deterministic eligibility, explainable ranking | **Done** |
| M6 | MCP tools behind adapter, comparison, saved opportunities, checklists | **Done** |
| M7 | Security review, performance, Windows packaging | **Done** - packaged build produced and audited |
| P1 | Catalog: sources registry, crawler, background run, dedup + sources | **Done** - 8 official portals shipped |
| P2 | Discover: search + filters over the catalog, eligibility hand-off | **Done** |

Full specification: [`goals.md`](goals.md) · Build log: [`achievements.md`](achievements.md)

---

## What works today

- Native Qt window with a real chat loop (Enter to send, Shift+Enter for newline).
- **Live model replies** through the local OpenCode service (stub still available
  and switchable in config).
- **My Profile page** — a local-only form (degree, GPA + scale, IELTS/TOEFL,
  countries, funding need) with completion tracking and no invented values.
- **Documents page** — upload a PDF, text file or image; text is read locally
  (PDF text layer, or Windows OCR for pictures); the model proposes fields; each
  proposal is checked **verbatim** against the document text and shown with a
  found / not-found marker; only rows you tick (and may edit) are merged.
- **Scholarship pages page** - paste the official scholarship URL: the page is
  fetched with strict guardrails (http/https only, HTML only, 2 MB cap,
  redirect-aware provenance, sha256 + retrieval timestamp), fields are proposed
  and must be **verbatim** in the page text; untick the ones you distrust.
- **Find pages on a site** - paste a university's (or a funding portal's)
  scholarships page and press **Find pages**: the app lists the scholarship
  and funding links that page itself publishes, same site only, documents
  skipped, capped and de-duplicated. Click one and it goes straight through
  the same read-and-verify flow. Nothing is guessed - every link is read from
  the page, and the chat's own web search is a separate, opt-in feature.
- **Catalog page** - a registry of **official portals** (8 shipped: Chevening,
  DAAD, Fulbright, Erasmus+, MEXT, Commonwealth, Korea GKS, Turkiye Burslari;
  your editable copy lives at `%APPDATA%\ScholarPath\sources_registry.toml`).
  Switch portals on, set how many pages each may contribute, and press
  **Start catalog run**: the app discovers scholarship pages from each portal's
  sitemap, feed and same-site links, obeys its `robots.txt`, reads **at most one
  page a second per host**, and only inside the paths the registry allows.
  Every value is still verified **word-for-word** against the page; a record is
  recognised by its title plus the portal's domain, so a second page **fills
  empty fields and adds a source** instead of duplicating the record, and a
  differing value is **kept** with the disagreement written down. The run shows
  progress, counts errors and can be cancelled between pages.
- **Discover page** - search the catalog by what the pages state. One search
  box (title, country, field, funder, amount, deadline wording) plus filters
  for level, country, field of study, portal and deadline state ("still open",
  "closing within 90 days", "already closed", "no readable date"). Results are
  ordered honestly (open deadlines first by date, then records with no readable
  date, then closed ones), and every card shows the page's own deadline
  sentence beside the parsed state. **Check against my profile** runs the same
  rule-based checks as the Eligibility page, and **Save** adds the record to
  Saved Opportunities. A match is a reading aid, never a verdict.
- **Re-check saved records** — press **Re-check pages** on the Eligibility or
  Saved page: every record's page is fetched again, the sha256 is compared
  with the copy that was saved, and the card is flagged when the page
  **changed** or when its stated **deadline has passed**. A page that cannot
  be reached says so instead of pretending.
- **Privacy switches** — voice input, the spoken reply and web search are all
  **off by default** (`[privacy]` in config.toml). The Settings page states
  exactly what each one sends and to whom; nothing leaves the device until
  you switch one on.
- **Eligibility page** — every saved record is checked by pure rule-based code
  against your local profile (nationality, degree level, language thresholds,
  grade average on a matching scale only, unambiguous deadlines). Results are
  satisfied / not satisfied / unknown / needs checking, each with the page text
  it was read from, ranked deterministically — **no model, no probabilities,
  and the word "eligible" is never claimed**; it only reports conflicts, gaps
  and "confirm on the official page".
- **Saved Opportunities page** — records you explicitly save (a Save ★ toggle
  on the eligibility and record cards; nothing auto-saves), side-by-side
  comparison labelled "a reading aid, not a ranking", and per-record
  application checklists drafted **only** from each page's own wording —
  if the page doesn't list documents or an application link, no steps are
  invented.
- **Chat captures your profile facts** — say "my name is …, I did IELTS 7.0"
  and every value is verified word-for-word against your own message, shown
  as an editable confirmation card in the transcript, and saved only to the
  rows you tick ("no need to re-enter or re-upload these later").
- **Voice input (speech to text)** — click the mic and speak; your words land
  as **editable text** in the composer for review before you press Enter
  (pause to finish, click again to stop early). While recording, the mic
  button plays an animated **listening ripple**. Uses the standard Python
  SpeechRecognition library: no Windows speech toggle, no model download, no
  API key — the audio clip is sent to Google's free speech service for
  transcription, and the app says so.
- **Live voice agent** — hit "Live voice" in the top bar and talk hands-free:
  the app listens, sends your words, and **speaks the reply aloud** in a
  natural neural voice (free Edge neural TTS — no API key; the offline
  Windows voice takes over automatically if the network is down), then
  listens again. The audio is synthesized by Microsoft's speech service and
  played on your own machine through the Windows audio engine. A voice bar
  always shows the real state (Listening / Thinking / Speaking) and names the
  voice in use, with an End button.
  Spoken text is markdown-free; the full reply stays in the chat, and the
  transcript follows the conversation as it grows. If a reply cannot be
  fetched, the app says so out loud and keeps listening instead of stopping.
- **Web search in the chat** — ask for current scholarships ("scholarships in
  the UK for a master's in engineering") and the app **searches the web** and
  answers from what it found, naming the pages it used. The search is
  keyless (no account, no API key). Results are treated as untrusted
  third-party data, official-looking domains (universities, governments,
  scholarship bodies) are listed first, and every result is marked as
  official-looking or not — so you always know which page to trust and
  confirm on. If the search cannot run, the app says so instead of answering
  from memory.
- **Replies read like a person wrote them** — the model is asked for plain,
  warm sentences with no formatting, and anything that still arrives as
  markdown is cleaned before you see it: no `**bold**`, no `--`, no headings,
  no table bars, no dash bullets. The chat bubble, the copy button and the
  spoken reply all get the same clean text.
- **The model behind it stays anonymous** — identity questions ("which model
  are you?") are answered deterministically without the model seeing them, a
  provider-neutral system prompt forbids disclosure, and any reply that names
  a model/provider token is withheld wholesale. Whichever provider is
  configured, the guard derives its tokens from config.
- **Tools (MCP) are opt-in and read-only** — off by default; configured in
  `config.toml` per server. With `read_only = true`, only tools advertising
  `readOnlyHint` may run; tool output is size-capped data, never instructions.
  The Settings page shows honest status and can check a server's tool list.
- Model registry + deterministic task routing (chat/classify/research/extract
  rules) built on the provider's advertised capabilities.
- Strict configuration: unknown keys and bad values are rejected, not ignored.
- Typed gateway contract — one seam for every model provider.
- Background execution so the window never freezes.
- Typed error surfaces: rate limit, timeout, unavailable, protocol error.
- Rotating logs that never contain message bodies or secrets.

## What it deliberately does not do yet

- **Nothing leaves your device unless you turn it on.** Voice input, the
  spoken reply and web search are all **off by default** (`[privacy]` in
  config.toml). When you switch one on, the Settings page says exactly what
  is sent and to whom.
- Search results are **candidates, not proof**. A page is only "verified"
  when the values literally appear in its text; the app tells you which
  results come from an academic or government domain and which do not, and
  you can add the domains you trust yourself.
- GPA scale conversion, funding-type ranking, and deadline-reminder features
  are intentionally deferred until there is a documented, honest policy for them.
- The catalog is a **starting set of eight official portals**, not a complete
  index: it finds pages through sitemaps, feeds and same-site links (no search
  engine, no JavaScript menus), reads HTML only (PDF prospectuses are skipped),
  and never goes faster than one request per second per host. Two portals were
  checked and left out because they could not be read: CSC (`csc.edu.cn`, HTTP
  412) and Australia Awards (`australiaawards.gov.au`, connection reset).
- Discover searches the **stored text**, so it is a reading aid, not a
  linguistic search: a word can match inside another word, level filters only
  match the page's own wording, "closing soon" is a fixed 90-day window, and
  there are no saved searches or deadline reminders. A page that changed since
  the last catalog run is caught by **Re-check**, not by searching again.
- MCP servers never start, and no model uses tools mid-conversation, until a
  concrete student-facing use and a documented injection policy exist.
- Extraction is a proposal engine, not an authority: a value the source does not
  literally contain is flagged and never applied without you typing it yourself.

That is the point: a smaller, truthful assistant beats an impressive one that
invents scholarships.

---

## Quick start

**Requirements:** Windows 10/11 · Python 3.11+ · a running OpenCode service for
live replies (the stub provider and the test suite work offline).

```powershell
git clone https://github.com/RajeshKc777/ScholarPath-.git
cd ScholarPath-
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
scholarpath
```

<details>
<summary><strong>Other commands</strong></summary>

```powershell
scholarpath --init-config   # write the configuration template, then exit
scholarpath --config path\to\config.toml
scholarpath --version
python -m scholarpath       # equivalent to the console script
pytest                      # 488 tests, no network required (fake server on loopback)
```

</details>

---

## Build the Windows app

The app also ships as a self-contained Windows build - no Python needed on
the machine that runs it:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

That installs PyInstaller, builds `dist\ScholarPathAI\ScholarPathAI.exe`
(a folder build: the exe plus its `_internal` runtime), and then **audits the
bundle** - it fails the build if a config, database, log, credential file or
a secret-looking value ever ends up inside it. The audit can also be run on
its own:

```powershell
.\.venv\Scripts\python.exe packaging\verify_bundle.py
```

Rules the build keeps:

- **No user data in the build.** Config, database and logs live in
  `%APPDATA%\ScholarPath` and are created on first run, never shipped.
- **No secrets in the build.** API keys are read from the user's config or
  the environment at run time.
- **The Python runtime is bundled**, so the app starts on a clean Windows.
- Measured startup of the packaged build on this machine: **~1.6 s** to the
  first window.

---

## Configuration

Config lives outside the package so it survives upgrades:

```
%APPDATA%\ScholarPath\config.toml     # Windows
~/ScholarPath/config.toml             # other platforms
```

```toml
[gateway]
provider = "stub"     # or "opencode" (Milestone 2) - talks to a running OpenCode service
model = ""            # "provider/model" or bare id; empty = OpenCode's default
timeout_seconds = 30.0
retries = 1

# opencode adapter overrides (empty = discover the running service automatically)
base_url = ""
service_file = ""
location_dir = ""

[ui]
theme = "dark"
window_width = 1100
window_height = 720

# What may leave this device. All three are OFF by default.
[privacy]
voice_stt = false   # microphone clip -> Google's speech service
voice_tts = false   # reply text -> Microsoft's speech service
web_search = false  # search question -> the web-search service

# Domains you trust for scholarship information (matched exactly).
[search]
trusted_domains = ["chevening.org"]

log_level = "INFO"
```

- `SCHOLARPATH_HOME` overrides the config folder; `--config` overrides the file.
- A missing file falls back to safe defaults. An **invalid** file is fatal
  (exit `2`) and names the offending field.
- Asking for a provider that is not implemented exits `3` with an explanation —
  it never silently downgrades to the stub.
- With `provider = "opencode"`, no secret goes in the config: the service
  password is read from OpenCode's registration file, or from the
  `OPENCODE_SERVICE_PASSWORD` environment variable when `base_url` is set.
- Template: [`config.example.toml`](config.example.toml) — contains no credentials.

### Sources registry (catalog)

The portals the **Catalog** page reads live in a separate file, so they can be
edited without touching config:

```
%APPDATA%\ScholarPath\sources_registry.toml   # your editable copy (created on first use)
src\scholarpath\data\sources_registry.toml    # the shipped default
```

Each `[[source]]` entry has `name`, `base_url`, `country`, `trust_level`
(`official` / `government`), `allowed_path_prefixes` (nothing outside them is
ever fetched), `crawl_depth` and `enabled`. Your copy wins; if it is broken the
Catalog page says so and refuses to run rather than silently falling back to the
shipped list.

---

## Architecture

```
src/scholarpath/
├── app.py                 entry point, startup checks, exit codes
├── config.py              TOML + pydantic models, strict validation
├── logging_setup.py       rotating logs, no payloads
├── storage.py             SQLite: profiles, documents, scholarships (+ catalog columns), sources, saved list, checklists
├── profiles.py            strict Profile model, merge_confirmed, completion
├── documents.py           PDF text layer (pypdf), plain text, Windows OCR images
├── extraction.py          prompt, JSON parsing, verbatim-verification against source
├── sources.py             guarded http(s) fetch: SSRF-safe resolution, caps, content-type, conditional GET, sha256, redirects
├── websearch.py           keyless web search: results, official-domain rule, untrusted-data block
├── discovery.py           scholarship links published by a page the student trusts, plus RSS/Atom helpers
├── registry.py            sources registry: shipped default, editable user copy, strict validation
├── crawler.py             robots.txt, sitemaps, feeds, same-site links, per-host pacing, page cap, 304s
├── catalog.py             the run: crawl → extract → verify → dedup/merge → save, honest stats, cancel
├── search.py              search + filters over the catalog: folded text, whole-word levels, deadline states
├── recheck.py             re-fetch a saved page: changed? deadline passed? reachable?
├── research.py            official-page pipeline: propose → verbatim verify → draft
├── eligibility.py         rule-based checks, honest verdicts, deterministic ranking
├── identity.py            provider anonymity: probe interception + reply withholding
├── chat_profile.py        chat-stated facts → verbatim-verified profile suggestions
├── prose.py               model markdown → plain prose for the bubble, the copy button and the voice
├── tts.py                 spoken replies: neural voice first, offline Windows voice as fallback
├── voice.py               speech-to-text input: capture, transcription, honest errors
├── mcp/
│   ├── __init__.py        exports
│   └── client.py          opt-in stdio MCP client: initialize/list/call, read-only guard
├── gateway/
│   ├── base.py            Message, ChatRequest/Response, typed errors, Protocol
│   ├── stub.py            offline, deterministic, self-describing
│   ├── registry.py        model catalogue, deterministic task routing
│   ├── opencode.py        adapter for the local OpenCode HTTP service
│   ├── openai_compat.py   adapter for any OpenAI-compatible endpoint
│   ├── chain.py           provider and model failover chain
│   ├── failover.py        rate-limit and quota handling
│   ├── credentials.py     key registration and rotation
│   └── factory.py         config → provider, explicit selection
└── ui/
    ├── chat_controller.py conversation state, busy handling, worker threads, web-search step
    ├── profile_page.py    local-only academic profile form
    ├── documents_page.py  upload → parse → propose → confirm → apply
    ├── research_page.py   official-page verification: URL → fields → save with provenance, plus Find pages
    ├── eligibility_page.py ranked rule-based eligibility reports with cited evidence    ├── saved_page.py       saved list, comparison grid, application checklists
    ├── catalog_page.py    official portals, background catalog run, progress, errors, stored records
    ├── discover_page.py   search + filters over the catalog, cards, save, profile hand-off
    ├── eligibility_dialog.py one record's rule-based checks, reusing the Eligibility card
    ├── recheck.py         the Re-check worker shared by the eligibility and saved pages
    ├── settings_page.py    honest status: model, local data, privacy switches, MCP tools
    ├── profile_suggestion.py transcript card confirming chat-stated facts
    ├── confirm_row.py     shared per-value confirm row (tick, edit, marker)
    ├── mic_button.py      microphone button with the listening ripple
    ├── theme.py           light Reddit-orange palette and widget styles
    └── main_window.py     stacked pages, sidebar, transcript, status strip, voice mode
```

**Layering rule:** nothing outside `gateway/` may know which model provider is in
use. Later milestones add `agents/`, `research/`, `storage/`, and `mcp/` behind
the same discipline — business logic stays testable without a network or a model.

---

## Quality gates

| Gate | How it is enforced |
| ---- | ------------------ |
| Tests | `pytest` — config validation, gateway contract, model routing, adapter round-trips against a fake server, chat turns, failure paths, verbatim extraction checks, SQLite profile/document/scholarship round-trips, fetch guardrails (including SSRF blocking) against a fake HTTP server, privacy switches, re-check logic, sources registry validation, crawler (robots, sitemaps, feeds, redirects, 304, pacing, page cap), the catalog run (dedup, merge, conflicts, invented values, cancel, old-database migration) and Discover (text folding, whole-word levels, five deadline states, filter isolation, ordering, empty states, the hand-off, navigation) |
| Honesty | Extraction values must appear verbatim in the source (document or fetched page); unverified proposals are visibly flagged and never auto-applied |
| Untrusted input | Fetched page content is data only, wrapped in markers with an explicit ignore-instructions instruction |
| Secrets | Never in source or config templates; config is local + git-ignored |
| Types | Type hints on public interfaces; frozen dataclasses for shared data |
| Errors | Typed gateway exceptions surfaced to the user, never swallowed |
| Logs | Event names and identifiers only — no message bodies, documents, or keys |
| Dependencies | Verified, not assumed; a broken system `mcp` install was caught this way |

---

## Privacy

- Profiles, documents, and verified scholarship records are stored locally in
  `%APPDATA%\ScholarPath\scholarpath.db`; uploaded files are parsed on this
  device (PDF text layer or Windows OCR).
- Chat messages are sent to the configured model service to produce a reply.
  When you extract fields, the document's **text** is sent to the service for a
  proposal. When you verify a scholarship page, that page's **text** is sent the
  same way. Files and the fetching of pages happen model-free on your machine.
- Fetching a page is a normal web visit by this app (its User-Agent is
  `ScholarPath-AI/0.1`); the site sees it like any other visitor.
- Facts you type into chat are sent to the model service twice: once for the
  reply, and once as a marked, data-only extraction task whose only allowed
  output is values verbatim from your own words. A suggestion is then shown
  to you; nothing is saved to your profile without your tick.
- The privacy disclosure rule runs in code, not good intentions: identity
  probes never reach the model, and a leaking reply is withheld wholesale.
- MCP servers are opt-in, read-only by default, and their output is treated
  exactly like fetched web content: data, capped, never executed.
- Nothing is uploaded to a ScholarPath server — there isn't one. Deletion
  controls live on the profile, documents, and research pages; deleting a
  scholarship record also removes its saved entry and checklist items.

---

## License

**Proprietary — view only. All rights reserved.**

This repository is public so the work can be inspected. It is **not** open
source, and no permission is granted to copy, modify, redistribute, or reuse any
part of it. Pull requests are not accepted.

See [`LICENSE`](LICENSE) for the exact terms. Permission requests:
[@RajeshKc777](https://github.com/RajeshKc777).

<br>

<div align="center">
<sub>ScholarPath AI is not affiliated with any university, government body, or scholarship provider.</sub>
</div>

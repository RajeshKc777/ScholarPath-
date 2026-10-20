<div align="center">

# ScholarPath AI

**Find scholarships you can actually get â€” with sources you can actually check.**

A local-first desktop assistant that matches students to legitimate scholarship
opportunities and explains, requirement by requirement, why they do or do not fit.

<br>

![Status](https://img.shields.io/badge/status-Milestone%204-4f8cff?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/Qt-6.12-41CD52?style=flat-square&logo=qt&logoColor=white)
![Tests](https://img.shields.io/badge/tests-207%20passing-2ea043?style=flat-square)
![License](https://img.shields.io/badge/license-view--only%20%C2%B7%20all%20rights%20reserved-b3261e?style=flat-square)

</div>

<br>

<div align="center">
  <img src="docs/screenshot.png" alt="ScholarPath AI desktop window showing the Reddit-orange dashboard" width="880">
  <br>
  <sub><em>Milestone 4 â€” documents and scholarship pages: local parsing and verbatim verification, no invented fields.</em></sub>
</div>

---

## Why this exists

Scholarship advice online is mostly guesses: unverified deadlines, invented
funding amounts, "you're eligible!" with no source behind it. ScholarPath AI is
built on the opposite rule set.

| Principle | What it means in practice |
| --------- | ------------------------- |
| **Official sources only** | Universities, government portals, and programme administrators are the authority â€” not search snippets. |
| **Explainable eligibility** | Every requirement is reported as satisfied, unmet, unknown, or needs manual verification. Never a bare "you qualify". |
| **No fabrication** | If a fact cannot be verified, the app says so. It does not invent deadlines, amounts, or criteria. |
| **Local-first** | Profiles and academic documents stay on your machine. Nothing leaves the device by default. |
| **Honest failure** | A broken provider produces an error, never a plausible-looking answer. |

---

## Status

> **Milestone 4 of 7 is complete.** Chat runs **live through the local OpenCode
> service**, profiles/documents work locally, and you can **verify a scholarship
> page**: paste the official URL, and only values that literally appear in the
> page text are offered â€” every saved record carries its source URL, retrieval
> time and page hash. There is **no automatic search yet**: you pick the pages.
> Eligibility checks are next.

| # | Milestone | Status |
| - | --------- | :----: |
| M1 | Repository, config, desktop shell, chat loop | **Done** |
| M2 | OpenCode gateway adapter, model registry, task routing | **Done** |
| M3 | Profiles, document ingestion, OCR, confirmed extraction | **Done** |
| M4 | Source discovery, official-source verification, storage | **Done** |
| M5 | Deterministic eligibility, explainable ranking | **Done** |
| M6 | MCP tools behind adapter, comparison, saved opportunities, checklists | **Done** |
| M7 | Security review, performance, Windows packaging | Planned |

Full specification: [`goals.md`](goals.md) Â· Build log: [`achievements.md`](achievements.md)

---

## What works today

- Native Qt window with a real chat loop (Enter to send, Shift+Enter for newline).
- **Live model replies** through the local OpenCode service (stub still available
  and switchable in config).
- **My Profile page** â€” a local-only form (degree, GPA + scale, IELTS/TOEFL,
  countries, funding need) with completion tracking and no invented values.
- **Documents page** â€” upload a PDF, text file or image; text is read locally
  (PDF text layer, or Windows OCR for pictures); the model proposes fields; each
  proposal is checked **verbatim** against the document text and shown with a
  found / not-found marker; only rows you tick (and may edit) are merged.
- **Scholarship pages page** â€” paste the official scholarship URL: the page is
  fetched with strict guardrails (http/https only, HTML only, 2 MB cap,
  redirect-aware provenance, sha256 + retrieval timestamp), fields are proposed
  and must be **verbatim** in the page text; untick the ones you distrust. There
  is no automatic search in this build â€” by design, you choose the sources.
- **Eligibility page** â€” every saved record is checked by pure rule-based code
  against your local profile (nationality, degree level, language thresholds,
  grade average on a matching scale only, unambiguous deadlines). Results are
  satisfied / not satisfied / unknown / needs checking, each with the page text
  it was read from, ranked deterministically â€” **no model, no probabilities,
  and the word "eligible" is never claimed**; it only reports conflicts, gaps
  and "confirm on the official page".
- **Saved Opportunities page** â€” records you explicitly save (a Save â˜… toggle
  on the eligibility and record cards; nothing auto-saves), side-by-side
  comparison labelled "a reading aid, not a ranking", and per-record
  application checklists drafted **only** from each page's own wording â€”
  if the page doesn't list documents or an application link, no steps are
  invented.
- **Chat captures your profile facts** â€” say "my name is â€¦, I did IELTS 7.0"
  and every value is verified word-for-word against your own message, shown
  as an editable confirmation card in the transcript, and saved only to the
  rows you tick ("no need to re-enter or re-upload these later").
- **Voice input (speech to text)** â€” click the mic and speak; your words land
  as **editable text** in the composer for review before you press Enter
  (pause to finish, click again to stop early). Uses the standard Python
  SpeechRecognition library: no Windows speech toggle, no model download, no
  API key â€” the audio clip is sent to Google's free speech service for
  transcription, and the app says so.
- **The model behind it stays anonymous** â€” identity questions ("which model
  are you?") are answered deterministically without the model seeing them, a
  provider-neutral system prompt forbids disclosure, and any reply that names
  a model/provider token is withheld wholesale. Whichever provider is
  configured, the guard derives its tokens from config.
- **Tools (MCP) are opt-in and read-only** â€” off by default; configured in
  `config.toml` per server. With `read_only = true`, only tools advertising
  `readOnlyHint` may run; tool output is size-capped data, never instructions.
  The Settings page shows honest status and can check a server's tool list.
- Model registry + deterministic task routing (chat/classify/research/extract
  rules) built on the provider's advertised capabilities.
- Strict configuration: unknown keys and bad values are rejected, not ignored.
- Typed gateway contract â€” one seam for every model provider.
- Background execution so the window never freezes.
- Typed error surfaces: rate limit, timeout, unavailable, protocol error.
- Rotating logs that never contain message bodies or secrets.

## What it deliberately does not do yet

- No scholarship search, no recommendations â€” there is no topic search in this
  build; you supply official pages. Eligibility checks read only what a page
  literally states; anything else is unknown or flagged for manual checking,
  and nothing is presented as verified advice beyond the page text.
- GPA scale conversion, funding-type ranking, and deadline-reminder features
  are intentionally deferred until there is a documented, honest policy for them.
- MCP servers never start, and no model uses tools mid-conversation, until a
  concrete student-facing use and a documented injection policy exist.
- Extraction is a proposal engine, not an authority: a value the source does not
  literally contain is flagged and never applied without you typing it yourself.

That is the point: a smaller, truthful assistant beats an impressive one that
invents scholarships.

---

## Quick start

**Requirements:** Windows 10/11 Â· Python 3.11+ Â· a running OpenCode service for
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
pytest                      # 207 tests, no network required (fake server on loopback)
```

</details>

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

log_level = "INFO"
```

- `SCHOLARPATH_HOME` overrides the config folder; `--config` overrides the file.
- A missing file falls back to safe defaults. An **invalid** file is fatal
  (exit `2`) and names the offending field.
- Asking for a provider that is not implemented exits `3` with an explanation â€”
  it never silently downgrades to the stub.
- With `provider = "opencode"`, no secret goes in the config: the service
  password is read from OpenCode's registration file, or from the
  `OPENCODE_SERVICE_PASSWORD` environment variable when `base_url` is set.
- Template: [`config.example.toml`](config.example.toml) â€” contains no credentials.

---

## Architecture

```
src/scholarpath/
â”œâ”€â”€ app.py                 entry point, startup checks, exit codes
â”œâ”€â”€ config.py              TOML + pydantic models, strict validation
â”œâ”€â”€ logging_setup.py       rotating logs, no payloads
â”œâ”€â”€ storage.py             SQLite: profiles, documents, scholarships, saved list, checklists
â”œâ”€â”€ profiles.py            strict Profile model, merge_confirmed, completion
â”œâ”€â”€ documents.py           PDF text layer (pypdf), plain text, Windows OCR images
â”œâ”€â”€ extraction.py          prompt, JSON parsing, verbatim-verification against source
â”œâ”€â”€ sources.py             guarded http(s) fetch: caps, content-type, sha256, redirects
â”œâ”€â”€ research.py            official-page pipeline: propose â†’ verbatim verify â†’ draft
â”œâ”€â”€ eligibility.py         rule-based checks, honest verdicts, deterministic ranking
â”œâ”€â”€ identity.py            provider anonymity: probe interception + reply withholding
â”œâ”€â”€ chat_profile.py        chat-stated facts â†’ verbatim-verified profile suggestions
â”œâ”€â”€ mcp/
â”‚   â”œâ”€â”€ __init__.py        exports
â”‚   â””â”€â”€ client.py          opt-in stdio MCP client: initialize/list/call, read-only guard
â”œâ”€â”€ gateway/
â”‚   â”œâ”€â”€ base.py            Message, ChatRequest/Response, typed errors, Protocol
â”‚   â”œâ”€â”€ stub.py            offline, deterministic, self-describing
â”‚   â”œâ”€â”€ registry.py        model catalogue, deterministic task routing
â”‚   â”œâ”€â”€ opencode.py        adapter for the local OpenCode HTTP service
â”‚   â””â”€â”€ factory.py         config â†’ provider, explicit selection
â””â”€â”€ ui/
    â”œâ”€â”€ chat_controller.py conversation state, busy handling, worker threads
    â”œâ”€â”€ profile_page.py    local-only academic profile form
    â”œâ”€â”€ documents_page.py  upload â†’ parse â†’ propose â†’ confirm â†’ apply
    â”œâ”€â”€ research_page.py   official-page verification: URL â†’ fields â†’ save with provenance
    â”œâ”€â”€ eligibility_page.py ranked rule-based eligibility reports with cited evidence
    â”œâ”€â”€ saved_page.py       saved list, comparison grid, application checklists
    â”œâ”€â”€ settings_page.py    honest status: model, local data, MCP tools
    â”œâ”€â”€ profile_suggestion.py transcript card confirming chat-stated facts
    â”œâ”€â”€ confirm_row.py     shared per-value confirm row (tick, edit, marker)
    â”œâ”€â”€ theme.py           light Reddit-orange palette and widget styles
    â””â”€â”€ main_window.py     stacked pages, sidebar, transcript, status strip
```

**Layering rule:** nothing outside `gateway/` may know which model provider is in
use. Later milestones add `agents/`, `research/`, `storage/`, and `mcp/` behind
the same discipline â€” business logic stays testable without a network or a model.

---

## Quality gates

| Gate | How it is enforced |
| ---- | ------------------ |
| Tests | `pytest` â€” config validation, gateway contract, model routing, adapter round-trips against a fake server, chat turns, failure paths, verbatim extraction checks, SQLite profile/document/scholarship round-trips, fetch guardrails against a fake HTTP server |
| Honesty | Extraction values must appear verbatim in the source (document or fetched page); unverified proposals are visibly flagged and never auto-applied |
| Untrusted input | Fetched page content is data only, wrapped in markers with an explicit ignore-instructions instruction |
| Secrets | Never in source or config templates; config is local + git-ignored |
| Types | Type hints on public interfaces; frozen dataclasses for shared data |
| Errors | Typed gateway exceptions surfaced to the user, never swallowed |
| Logs | Event names and identifiers only â€” no message bodies, documents, or keys |
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
- Nothing is uploaded to a ScholarPath server â€” there isn't one. Deletion
  controls live on the profile, documents, and research pages; deleting a
  scholarship record also removes its saved entry and checklist items.

---

## License

**Proprietary â€” view only. All rights reserved.**

This repository is public so the work can be inspected. It is **not** open
source, and no permission is granted to copy, modify, redistribute, or reuse any
part of it. Pull requests are not accepted.

See [`LICENSE`](LICENSE) for the exact terms. Permission requests:
[@RajeshKc777](https://github.com/RajeshKc777).

<br>

<div align="center">
<sub>ScholarPath AI is not affiliated with any university, government body, or scholarship provider.</sub>
</div>

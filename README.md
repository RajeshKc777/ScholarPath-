<div align="center">

# ScholarPath AI

**Find scholarships you can actually get — with sources you can actually check.**

A local-first desktop assistant that matches students to legitimate scholarship
opportunities and explains, requirement by requirement, why they do or do not fit.

<br>

![Status](https://img.shields.io/badge/status-Milestone%201-4f8cff?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/Qt-6.12-41CD52?style=flat-square&logo=qt&logoColor=white)
![Tests](https://img.shields.io/badge/tests-25%20passing-2ea043?style=flat-square)
![License](https://img.shields.io/badge/license-view--only%20%C2%B7%20all%20rights%20reserved-b3261e?style=flat-square)

</div>

<br>

<div align="center">
  <img src="docs/screenshot.png" alt="ScholarPath AI desktop window showing a conversation with the offline stub gateway" width="880">
  <br>
  <sub><em>Milestone 1 shell — an honest offline build: it says what it does not do.</em></sub>
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

> **Milestone 1 of 7 is complete.** The desktop shell, configuration, and chat
> pipeline work end to end against an **offline stub gateway**. There is no
> network access, no model, and no research in this build — and the interface
> says so on every reply.

| # | Milestone | Status |
| - | --------- | :----: |
| M1 | Repository, config, desktop shell, chat loop | **Done** |
| M2 | OpenCode gateway adapter, model registry, task routing | Next |
| M3 | Profiles, document ingestion, OCR, confirmed extraction | Planned |
| M4 | Source discovery, official-source verification, storage | Planned |
| M5 | Deterministic eligibility, explainable ranking | Planned |
| M6 | MCP tools, comparison, saved opportunities, checklists | Planned |
| M7 | Security review, performance, Windows packaging | Planned |

Full specification: [`goals.md`](goals.md) · Build log: [`achievements.md`](achievements.md)

---

## What works today

- Native Qt window with a real chat loop (Enter to send, Shift+Enter for newline).
- Strict configuration: unknown keys and bad values are rejected, not ignored.
- Typed gateway contract — one seam for every model provider.
- Background execution so the window never freezes.
- Typed error surfaces: rate limit, timeout, unavailable, protocol error.
- Rotating logs that never contain message bodies or secrets.

## What it deliberately does not do yet

- No scholarship search, no eligibility checks, no recommendations.
- No model calls of any kind.
- No storage of profiles or documents.

The stub gateway states this in every response. That is the point: a smaller,
truthful assistant beats an impressive one that invents scholarships.

---

## Quick start

**Requirements:** Windows 10/11 · Python 3.11+ · no network needed for this build.

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
pytest                      # 25 tests, no network, no Qt event loop required
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
provider = "stub"     # "opencode" arrives in Milestone 2
model = ""
timeout_seconds = 30.0
retries = 1

[ui]
theme = "dark"
window_width = 1100
window_height = 720

log_level = "INFO"
```

- `SCHOLARPATH_HOME` overrides the config folder; `--config` overrides the file.
- A missing file falls back to safe defaults. An **invalid** file is fatal
  (exit `2`) and names the offending field.
- Asking for a provider that is not implemented exits `3` with an explanation —
  it never silently downgrades to the stub.
- Template: [`config.example.toml`](config.example.toml) — contains no credentials.

---

## Architecture

```
src/scholarpath/
├── app.py                 entry point, startup checks, exit codes
├── config.py              TOML + pydantic models, strict validation
├── logging_setup.py       rotating logs, no payloads
├── gateway/
│   ├── base.py            Message, ChatRequest/Response, typed errors, Protocol
│   ├── stub.py            offline, deterministic, self-describing
│   └── factory.py         config → provider, explicit selection
└── ui/
    ├── chat_controller.py conversation state, busy handling, worker threads
    └── main_window.py     Qt window, transcript, input, status
```

**Layering rule:** nothing outside `gateway/` may know which model provider is in
use. Later milestones add `agents/`, `research/`, `storage/`, and `mcp/` behind
the same discipline — business logic stays testable without a network or a model.

---

## Quality gates

| Gate | How it is enforced |
| ---- | ------------------ |
| Tests | `pytest` — config validation, gateway contract, chat turns, failure paths |
| Secrets | Never in source or config templates; config is local + git-ignored |
| Types | Type hints on public interfaces; frozen dataclasses for shared data |
| Errors | Typed gateway exceptions surfaced to the user, never swallowed |
| Logs | Event names and identifiers only — no message bodies, documents, or keys |
| Dependencies | Verified, not assumed; a broken system `mcp` install was caught this way |

---

## Privacy

- Student profiles, academic documents, and research history are stored locally.
- Nothing is sent to an external provider by this build.
- Deletion controls and an explicit "this leaves your device" indicator are
  required before any network-backed milestone ships.

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

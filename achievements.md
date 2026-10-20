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

- Repository: populated, pushed to `https://github.com/RajeshKc777/ScholarPath-`
  (`main`, commit `ff6ee27`).
- Working app: **yes** — M1 launches, chats through the offline stub, reports errors.
- Tests: **25 passing** (`pytest`, 0.12 s).
- Next milestone: **M2** (G202) — OpenCode gateway adapter.

---

## Log (newest first)

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

- G101, G102, G104–G111, G114 — product capabilities beyond the M1 shell.
- Milestones G202–G207.

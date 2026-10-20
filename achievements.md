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

- Repository: **empty** — only `.qodo/` (empty agent/workflow folders). No code,
  no `pyproject.toml`, no git repo yet.
- Product features: **none**.
- Next milestone: **M1** (G201).

---

## Log (newest first)

### 2026-10-20 — A2 · Environment baseline verified

**Satisfies:** G115 (verify before building), G103 (technology direction)

Machine facts, measured rather than assumed:

| Item | Finding |
| ---- | ------- |
| Default `python` | 3.11.9 — `C:\Users\LOQ\AppData\Local\Programs\Python\Python311\python.exe` |
| Also installed | 3.13 (`py -3.13`), and the `py` launcher |
| pip | 26.2.1 |
| PySide6 | 6.11.1 (Qt 6.11.1) — imports and works |
| pydantic | 2.12.5 |
| fastapi | 0.128.0 |
| pytest | 9.0.2 |
| httpx | 0.28.1 |
| sqlite3 | 3.45.1 |
| `mcp` | **1.25.0 installed but broken** — `ModuleNotFoundError: mcp.server.fastmcp.resources.templates` |
| uv | not installed |
| git | 2.55.0 |

**Implication:** a project venv is mandatory; the global env cannot be trusted
(`mcp` proves it). Python 3.11 is the safe target for PySide6 + PyInstaller.

---

### 2026-10-20 — A1 · Goals / achievements tracking process

**Satisfies:** G2, G3

- `goals.md` — full product specification (G101–G115) with requirement register,
  milestone table, dependency checklist, open questions.
- `achievements.md` — this file.
- `AGENTS.md` — project memory carrying the maintenance rule.
- Global config (`~/.config/opencode/AGENTS.md`) points at this project's rule.

**Evidence:** files present in `C:\Users\LOQ\OneDrive\Desktop\ScholarPath`.

---

## Not yet achieved

- All product goals G101–G114 — nothing built yet.
- Milestones G201–G207 — not started.

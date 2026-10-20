# Antigravity UI Brief — ScholarPath AI

**Audience:** the Antigravity coding agent.
**Task:** redesign the desktop user interface of ScholarPath AI.
**Date:** 2026-10-20 · **Repo:** `C:\Users\LOQ\OneDrive\Desktop\ScholarPath`
**Current milestone:** M1 complete · **Your scope:** presentation layer only

---

## 0. Read this first

Before writing any code, read these files in the repo root. They are the source of
truth and they override anything in this brief if they disagree:

1. `AGENTS.md` — how this project is maintained (two-document rule).
2. `goals.md` — the product specification and requirement register (`G1xx`).
3. `achievements.md` — what is actually built and verified.
4. `README.md` — public description and setup.
5. `src/scholarpath/ui/main_window.py` and `ui/chat_controller.py` — the current UI.

If you cannot verify a claim, do not write it into the UI.

---

## 1. What exists today (do not rebuild it)

```
src/scholarpath/
├── app.py                 startup, CLI flags, exit codes 2 (config) / 3 (gateway)
├── config.py              TOML + pydantic, strict, config at %APPDATA%\ScholarPath\config.toml
├── logging_setup.py       rotating logs, no payloads
├── gateway/base.py        Message, ChatRequest, ChatResponse, typed errors, ModelGateway
├── gateway/stub.py        offline deterministic reply, states it does nothing
├── gateway/factory.py     config -> provider (opencode is NOT implemented yet)
└── ui/
    ├── chat_controller.py conversation state, busy flag, worker-thread dispatch
    └── main_window.py     single window: header, transcript, composer, status
```

Working behaviour you must keep:

- One window, one conversation, one turn at a time (`ChatController.send` returns
  `False` while busy — respect it, disable the composer).
- Signals available: `turn_added(Turn)`, `busy_changed(bool)`, `failed(str)`.
- `Turn` fields: `role`, `text`, `timestamp`, `model`, `error`.
- Gateway failures arrive as `Turn(error=True)` **and** a `failed` signal — show both
  consistently, never replace them with a friendly success-looking bubble.
- Tests: `pytest` — currently 25 passing. They must still pass.

**Not built, and you must not simulate:** scholarship search, eligibility checks,
ranking, result cards with real data, profiles, document upload, OCR, saved lists,
filters, comparison, MCP tools, OpenCode model calls.

---

## 2. Hard constraints

These are product law, not preferences. Violating any one fails the task.

1. **No fabricated content.** No placeholder scholarships, universities, deadlines,
   funding amounts, logos, or "example" results that could be mistaken for real data.
2. **No fake states.** No simulated typing that implies a model is working, no
   progress bars for work that is not happening, no disabled buttons that look live.
3. **Honest labels.** If it is not implemented, it is either absent or visibly
   labelled `Coming in Milestone N` and disabled. Never a dead control that looks
   clickable.
4. **No new runtime dependencies** without asking. `PySide6-Essentials` only — there
   is **no QtWebEngine**, no QML, no web view, no icon-font package. Draw what you
   need with `QPainter`, QSS, inline SVG via `QSvgRenderer` (part of Essentials) or
   simple text glyphs.
5. **No secrets, no hardcoded paths.** Use `scholarpath.config.app_data_dir()` and
   `config_path()`.
6. **Keep the architecture.** UI may depend on the controller and config; it may not
   import a provider, open a network connection, or write to the database that does
   not exist yet.
7. **Python 3.11 / Qt 6.12 / Windows-first.** No APIs missing from Qt 6.12.
8. **Do not touch** `gateway/*`, `config.py` semantics, or `app.py` exit codes without
   a written reason in `achievements.md`.

---

## 3. Design direction

**Mood:** calm, editorial, trustworthy. A research desk, not a chatbot toy.
The student is anxious about money and admissions — the interface should feel
quiet, precise, and adult. No gradients-as-decoration, no neon, no glassmorphism.

**Reference points:** Linear's restraint, Arc's typography, a well-set PDF report.
Think "financial document you can trust", not "AI product landing page".

### Tokens (use exactly these; put them in `ui/theme.py`)

| Token | Value | Use |
| ----- | ----- | --- |
| `bg.base` | `#0F1218` | window background |
| `bg.surface` | `#161B24` | panels, transcript |
| `bg.raised` | `#1D2430` | composer, hovered rows |
| `border.subtle` | `#242C3A` | 1 px separators |
| `border.focus` | `#5B8CFF` | focus ring, active input |
| `text.primary` | `#E8ECF4` | body |
| `text.secondary` | `#A7B0C0` | labels, metadata |
| `text.muted` | `#6E7A8F` | timestamps, hints |
| `accent` | `#5B8CFF` | primary action, links |
| `accent.hover` | `#7BA4FF` | hover |
| `danger` | `#FF8F8F` | errors only |
| `success` | `#69D19B` | reserved; do not use yet |

- **Type:** `Segoe UI Variable` falling back to `Segoe UI`, then `sans-serif`.
  Sizes: 22 px page title · 15 px body · 13 px secondary · 11 px micro-label
  (uppercase, 0.08 em tracking) · 12 px monospace (`Cascadia Mono`, `Consolas`) for
  paths and IDs.
- **Spacing scale:** 4 / 8 / 12 / 16 / 24 / 32. Nothing off-scale.
- **Radius:** 8 px controls, 12 px panels, 999 px for chips.
- **Elevation:** one level only — a 1 px border, no drop shadows except the window
  chrome. Depth comes from surface tint, not blur.
- **Motion:** 120–160 ms ease-out on hover and panel reveal. Nothing loops.

### Layout

- Window: 1100×720 default, minimum 900×620, centred on first launch.
- Content max width 860 px, centred; the transcript may use the full panel, but
  text lines must not exceed ~72 characters.
- 24 px outer margin, 16 px panel padding, 24 px between logical sections.
- Header: 56 px tall — wordmark left, one quiet status pill right.
- Composer: 88–104 px, pinned to the bottom, grows to 160 px max, then scrolls.
- Status strip: 24 px, single line, never wraps into two rows.

---

## 4. Screens and states

### 4.1 Chat — empty state (the first thing a student sees)

- Wordmark **ScholarPath AI**, one-line promise, and a short honest note:
  *"Milestone 1 · offline build. No research yet — the assistant will say so."*
- Three suggestion chips that only **prefill the composer** (they must not send):
  - "I finished my bachelor's in Computer Science."
  - "I'm applying for a PhD in Germany for 2027."
  - "What funding exists for master's study in Canada?"

  Chips are neutral prompts, not promises of results.
- A small metadata block: config path, gateway name, model name, all from
  `ChatController` / `config_path()`. Monospace, muted.
- No fake "recent searches", no fake history, no metrics.

### 4.2 Chat — conversation

- Turns are **editorial blocks**, not bubbles: a micro-label above the text
  (`YOU` / `SCHOLARPATH · <model>`), body text below, 24 px apart, hairline divider
  between turns at 40% opacity.
- User text: `text.primary`. Assistant text: `text.primary`; when `Turn.error` is
  true, `danger` and a left rule (2 px) instead of a coloured background.
- Timestamps on hover only (tooltip), never permanently, to keep the page quiet.
- Long assistant text: max width 72ch, 1.55 line-height, preserve paragraphs.
- Copy button per assistant turn on hover (`Copy` → `Copied` for 1.2 s).
  Implement with `QApplication.clipboard()`, no toast.
- New content auto-scrolls only when the user is already at the bottom; if they
  scrolled up, show a "↓ New message" pill instead of yanking the view.

### 4.3 Chat — working

- Composer disabled, send button becomes a static progress ring drawn with
  `QPainter` (indeterminate arc, 16 px). No fake "thinking" text beyond
  `Working…` in the status strip.
- Do **not** stream characters into the transcript.

### 4.4 Error

- Error turn in the transcript (danger, left rule) with the message the controller
  produced, verbatim. No rewrite that softens it.
- A single retry affordance that re-sends the last user message **only if** the
  controller is idle. Label it `Retry` and nothing else.
- Status strip shows the same failure once; do not duplicate it three ways.

### 4.5 Settings (read-only in M1)

- Modal dialog, 520 px wide. Shows effective values: gateway provider, model,
  timeout, retries, theme, log level, config file path, log folder path.
- Buttons: `Open config folder` (opens Explorer at `app_data_dir()`),
  `Copy path`, `Close`.
- Editing config inside the app is **M2+**. Say so with one muted line:
  *"Editing settings in-app arrives with the gateway milestone."*
- Never display a value the config does not actually contain.

### 4.6 About

- Version from `scholarpath.__version__`, licence line (`Proprietary — view only`),
  links: repo, `goals.md`, `achievements.md` (open with `QDesktopServices`).
- One sentence on what the app will become, and one on what it does not do today.

---

## 5. Copy rules

- Plain language, second person, no exclamation marks, no hype adjectives.
- Never write "found scholarships", "matching…", "searching the web" in M1.
- Errors state what happened and what to do: *"The model did not respond in time.
  Nothing was saved — try again."*
- Empty states describe the next real action, not aspirational features.
- All user-visible strings live in one place (`ui/copy.py`) so they can be audited.

---

## 6. Interaction and accessibility

- Keyboard: `Tab` reaches header action → transcript (copy targets) → composer →
  send. `Enter` sends, `Shift+Enter` newline, `Ctrl+,` settings, `Ctrl+Q` quit,
  `Ctrl+Shift+C` copy last reply.
- Visible focus ring on every interactive element (`border.focus`, 2 px, offset 2).
- Contrast: body text ≥ 4.5:1 on its surface; muted text only for non-essential
  metadata. Verify before shipping.
- All icon-only controls have tooltips **and** accessible names
  (`setAccessibleName`).
- Respect system font scaling; do not fix heights where text can grow.
- No colour-only meaning: errors also carry the word "Error".

---

## 7. Technical plan (suggested)

```
src/scholarpath/ui/
├── theme.py        tokens + QSS builder + font loading  (new)
├── copy.py         every user-visible string            (new)
├── widgets/
│   ├── turn_view.py      one turn block + copy affordance
│   ├── composer.py       growing input, send button, chips
│   ├── status_strip.py   gateway/model/state line
│   └── dialogs.py        settings + about
├── chat_controller.py    unchanged contract
└── main_window.py        layout composition only
```

Rules:

- `MainWindow` composes widgets; it does not paint or build HTML strings inline.
- Render turns with `QTextBrowser`/custom `QWidget` — **not** a web view. Escape
  every dynamic string (`html.escape`), then convert `\n` to `<br>`.
- Do not re-render the whole transcript on each token; there is no streaming.
  Re-render on `turn_added` is acceptable and already proven.
- Keep the window responsive: any gateway call stays on the controller's dispatch.
- No `time.sleep` on the UI thread.

---

## 8. Acceptance checklist

Functional

- [ ] `pytest` green (25+ tests).
- [ ] App launches: `scholarpath` (or `python -m scholarpath`).
- [ ] Send with Enter; newline with Shift+Enter; composer disabled while busy.
- [ ] `Retry` re-sends only when idle and only after a failure.
- [ ] Copy works on assistant turns; clipboard verified manually.
- [ ] Settings shows the **real** effective config and the real paths.
- [ ] About shows the real version.
- [ ] Keyboard-only path reaches every control.

Honesty

- [ ] No fabricated scholarships, numbers, deadlines, or universities anywhere.
- [ ] No control implies unimplemented functionality.
- [ ] Stub replies still state that nothing was researched.
- [ ] Errors are word-for-word from the controller.

Visual

- [ ] Tokens from §3 only; no stray hex values.
- [ ] 900×620 minimum window with no clipping or overlap.
- [ ] Long message (2 000 chars) and 30-turn conversation render acceptably.
- [ ] `docs/screenshot.png` replaced with a **real** capture of the new UI.

---

## 9. Deliverables

1. Code changes inside `src/scholarpath/ui/` (plus `tests/` if you add pure helpers).
2. Updated `docs/screenshot.png` — capture with:
   ```powershell
   .\.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication; ..."
   ```
   (see `achievements.md` A4 for the exact grab pattern; window must be shown and
   `processEvents()` looped before `grab()`).
3. `goals.md` — add the new requirement row and mark it done.
4. `achievements.md` — new `An` entry: what changed, evidence, limits.
5. `README.md` — only the screenshot/feature wording if it actually changed.

Follow `AGENTS.md`: requirement first, achievement second, same session, nothing deleted.

---

## 10. Out of scope (do not start)

Profiles, document upload, OCR, eligibility, ranking, research, MCP, model calls,
SQLite, packaging, auto-update, telemetry, accounts, sync, mobile, web.

If you believe one is required to make the UI coherent, write the question into
`goals.md` under *Open questions* — do not implement it.

---

## 11. Definition of done

A student opens the window, immediately understands that this is an early, honest
build, can type a question and read a truthful answer, can find the real
configuration, and never sees a single invented fact or a control that lies about
what it does.

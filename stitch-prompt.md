# Stitch Prompt — ScholarPath AI UI

> **Status 2026-10-20: historical.** The muted palette these prompts describe was
> superseded in the implemented app by the light dashboard + Reddit-orange
> recolour (see `goals.md` §19a, `theme.py`). Keep this file for reference if
> Stitch renders are ever wanted again — regenerate with the tokens from
> `theme.py`, not the block below.

Paste these into Google Stitch, **in order**. Project device type: **Desktop**.
The design brief itself lives in [`antigravityUI.md`](antigravityUI.md); this file
is only the prompt layer.

> **What Stitch output is for:** visual reference — layout, spacing, hierarchy,
> colour use. It generates HTML, and this app is PySide6/Qt, so the HTML is **not**
> shippable. The tokens are the contract; the implementation follows
> `antigravityUI.md`.

**Rendered reference (already generated):**

| Screen | File | Stitch screen |
| ------ | ---- | ------------- |
| Chat · empty state | [`docs/stitch-empty-state.png`](docs/stitch-empty-state.png) | `projects/551533196934687083/screens/d548bb6780ae4bcbbb7703972a44f5f0` |
| Chat · conversation + error | [`docs/stitch-conversation.png`](docs/stitch-conversation.png) | `projects/551533196934687083/screens/7714757823734a27a758c521bff36c0a` |

Project: `projects/551533196934687083` (`ScholarPath AI UI`).

---

## Prompt 0 — project setup (optional)

If Stitch asks for a starting point, use:

```
A desktop application for university students researching scholarship funding.
Dark, editorial, trustworthy. Calm research desk, not a chatbot toy.
```

---

## Prompt 1 — Chat, empty state

```
Desktop app screen, 1440x900, dark editorial theme, for "ScholarPath AI" — a calm
scholarship-research assistant for university students. Visual language: Linear's
restraint crossed with a well-set financial report. No gradients, no glassmorphism,
no neon, no decorative illustrations, no mock data.

Palette: page background #0F1218, panels #161B24, raised controls #1D2430, 1px
hairline borders #242C3A, primary text #E8ECF4, secondary #A7B0C0, muted #6E7A8F,
accent blue #5B8CFF, danger red #FF8F8F.

Typography: Inter (fallback Segoe UI). 22px semibold page title, 15px body at 1.55
line-height, 11px uppercase micro-labels with 0.08em letter-spacing, 12px monospace
for file paths. Spacing on a 4/8/12/16/24/32 scale. 8px radius on controls, 12px on
panels. One elevation level only: 1px borders, no drop shadows.

Layout: 56px header — wordmark "ScholarPath AI" on the left, a small quiet pill on
the right reading "Milestone 1 · offline". Centred content column, max width 860px.

Empty state: a large heading "Find funding you can actually verify.", one short
subtitle, then a muted line "Offline build — no research yet. The assistant will
say so." Below that, three outlined prompt chips in a row with neutral study
intents: "I finished my bachelor's in Computer Science", "PhD in Germany, 2027
intake", "Funding for a master's in Canada". Under the chips, a small monospace
block showing the real config path "C:\Users\LOQ\AppData\Roaming\ScholarPath\config.toml".

Bottom: composer panel pinned to the bottom of the window — a two-line text area
with placeholder "Describe your study plans…", a small hint "Enter to send ·
Shift+Enter for a new line", and a compact primary Send button in accent blue with
dark text. Very bottom: 24px status strip, one line, muted: "Ready · gateway: stub ·
model: default · no research performed in this build".

The empty state must feel quiet, precise and adult. No cards, no metrics, no fake
history, no invented scholarships.
```

---

## Prompt 2 — Chat, conversation + error

```
Same app, same palette, same typography, same spacing tokens. Conversation state.
Turns are editorial blocks, not chat bubbles: each turn has an 11px uppercase muted
micro-label ("YOU" or "SCHOLARPATH · stub/deterministic"), then body text at 15px
with lines no wider than 72 characters, 24px gap between turns, and a hairline
divider at 40% opacity between them.

Show three turns:
1. User: "I finished my bachelor's in Computer Science, IELTS 7.0."
2. Assistant: "Offline stub gateway (Milestone 1)." followed by a paragraph:
   "No scholarship research has been performed. This build has no network access
   and no model behind it — real discovery and eligibility checks arrive in later
   milestones." A small copy icon sits at the top-right of the assistant block,
   visible on hover only.
3. Error turn: a 2px danger-red left rule, red body text "The model provider is
   rate limiting requests. Wait a moment and retry.", and a small text-only "Retry"
   button aligned left beneath it.

Composer at the bottom is disabled while working: input dimmed, Send button replaced
by a 16px indeterminate progress ring, status strip reads "Thinking… · gateway: stub
· model: default · no research performed in this build".

Austere, document-like, no shadows, no emoji, no fabricated scholarship content.
```

---

## Prompt 3 — Settings dialog (read-only)

```
A modal dialog over the same dark app, 520px wide, 12px radius, surface #161B24,
1px border #242C3A. Title "Settings". A quiet note under it: "Editing settings
in-app arrives with the gateway milestone."

A read-only key/value list with hairline row dividers, 13px labels in secondary grey
and 13px values in primary text, monospace for paths:
Gateway provider: stub · Model: default · Timeout: 30.0 s · Retries: 1 ·
Theme: dark · Log level: INFO · Config file: C:\Users\LOQ\AppData\Roaming\ScholarPath\config.toml ·
Logs: C:\Users\LOQ\AppData\Roaming\ScholarPath\logs

Footer: two secondary buttons "Open config folder" and "Copy path" on the left, one
primary "Close" on the right. No sliders, no toggles, no editable fields — this is a
truthful view of the effective configuration, nothing more.
```

---

## Iteration prompts (use after the first render)

| Problem | Prompt to send |
| ------- | -------------- |
| Too "AI product" | `Reduce decoration. Remove gradients, glows and shadows. Make it look like a well-typeset research document: more whitespace, fewer containers, 1px hairlines only.` |
| Chips look like ads | `Make the three chips neutral and quiet: outlined, 1px border, muted text, no fill, no icons, no colour.` |
| Assistant text too wide | `Constrain body text to 72 characters per line and increase line-height to 1.55.` |
| Colours drifted | `Restore exact tokens: bg #0F1218, panel #161B24, raised #1D2430, border #242C3A, text #E8ECF4, secondary #A7B0C0, muted #6E7A8F, accent #5B8CFF, danger #FF8F8F.` |
| Invented data appeared | `Remove every scholarship name, university, amount, date and logo. The screen must contain no invented facts at all.` |
| Too crowded | `Apply the spacing scale strictly: 4/8/12/16/24/32. 24px between turns, 16px panel padding, 24px window margin.` |

---

## Guardrails (repeat these if Stitch drifts)

- No fake scholarships, universities, deadlines, amounts, or logos — anywhere.
- No fake progress, typing animation, or "searching…" states.
- No disabled control that looks live; unimplemented features are simply absent.
- Dark theme only; light mode is a later milestone.
- Desktop only; do not produce mobile layouts.

# ScholarPath — project memory

Working directory: `C:\Users\LOQ\OneDrive\Desktop\ScholarPath`

## The two-document rule (mandatory)

Two files track this project. They are never optional, never stale.

| File | Holds | Update when |
| ---- | ----- | ----------- |
| `goals.md` | What the system must do | The user states a **new requirement, change, or decision** |
| `achievements.md` | What is actually built and verified | A **feature is finished** |

Rules:

1. **Requirement first.** A new requirement is written into the requirements log
   in `goals.md` (dated, new `Gn` ID, status `[ ]`) *before* any code is written.
2. **Completion second.** When the feature works and is verified, append an entry
   to `achievements.md` (dated, `An` ID, names the `Gn` it satisfies, evidence,
   known limits) and flip the goal to `[x]`.
3. **Same turn.** Both updates happen in the session that made the change. Never
   defer them to "later" and never ask to update them — just do it.
4. **Nothing is deleted.** Superseded requirements are struck through with a
   pointer to the replacement; achievements are never rewritten.
5. **Scope honesty.** If scope is undefined, `goals.md` says so. Do not invent
   product features to fill empty sections.

## Style

- Short and factual. One line per requirement, one block per achievement.
- Reference file paths instead of pasting code.
- Keep `goals.md` and `achievements.md` cross-linked by ID (`G2` ↔ `A1`).

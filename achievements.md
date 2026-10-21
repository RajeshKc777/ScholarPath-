# ScholarPath AI — Achievements

Last updated: 2026-10-21

What has actually been **built and verified**. A feature appears here only when it
is finished, not when it is started. Each entry names the goal it satisfies
(`Gn` from [goals.md](goals.md)) so the two files stay in sync.

## Definition of done

1. The work exists in the repo (not just in chat).
2. It was run, opened, or checked — there is evidence.
3. The matching goal in `goals.md` is marked `[x]`.

---

## Current state

- Repository: populated and pushed to `https://github.com/RajeshKc777/ScholarPath-`
  (`main`).
- Working app: **yes** — M1–M5 plus **M6**: saved opportunities with explicit
  save toggles, side-by-side comparison, per-record application checklists
  drafted only from verbatim record values, an honest Settings page, and
  opt-in read-only MCP tools behind a stdlib adapter. Plus two owner mandates:
  the model/provider can never be disclosed in chat (probes answered
  deterministically, leaky replies withheld), and profile facts stated in chat
  are proposed for saving through an explicit, verbatim-verified confirmation
  card. **Phase 1 of the discovery roadmap** adds the sources registry, the
  crawler and the background catalog run (A26); **phase 2** adds the Discover
  page - search and filters over the stored records with an eligibility
  hand-off (A27).
- Licence: proprietary, source-available, view-only (`LICENSE`).
- Tests: **488 passing** (`pytest`, ~42 s).
- Next: **Phase 3** of the owner roadmap (to be scoped with the owner before
  any code); M7 packaging and the security review remain in place.

---

## Log (newest first)

### 2026-10-21 — A27 — Phase 2: Discover search, filters and the profile hand-off (G149-G151)

**Satisfies:** G149 (search + filters), G150 (eligibility hand-off + save),
G151 (local-only, browsing writes nothing). Builds on A26's catalog records.

| Area | File(s) |
| ---- | ------- |
| Matching: accent/case/quote/dash folding, whole-word levels, deadline states | `src/scholarpath/search.py` |
| One profile-payload reader for both pages | `src/scholarpath/profiles.py` (`stored_profile_payload`) |
| Discover page: search box, five filters, counts, cards, empty states | `src/scholarpath/ui/discover_page.py` |
| The record's checks in a dialog, reusing the Eligibility page's card | `src/scholarpath/ui/eligibility_dialog.py` |
| Sidebar entry, page at index 6, reload on open, index map | `src/scholarpath/ui/main_window.py` |
| Tests | `tests/test_search.py` (26), `tests/test_discover_page.py` (14), `tests/test_navigation.py` (2) |

Behaviour: **Discover** searches the records the catalog already holds. Text
search folds accents ("turkiye" finds "Türkiye") and every word must appear;
level is read from the page's own wording as whole words ("doctoral" matches
PhD, "BSc and MA" matches both, "Bacheloropolis" matches neither); the deadline
filter uses the stored, parsed date only, so an ambiguous "05/11/2026" stays
"no readable date" instead of being guessed; other filters read only their own
field (a record titled "Netherlands Grant" with country Germany is not a
country match). Results are ordered open-first by date, then undated, then
closed. Each card shows the page's sentence ("The page says: ...") beside the
parsed state. **Check against my profile** opens the deterministic checks on
that record's verified values; **Save** adds it to Saved Opportunities.

**Evidence:** **488 passing** in ~42 s. New tests cover the folding and
whole-word rules, the five deadline states and their phrases, field-isolation
of every filter, deterministic ordering, honest empty states, saving from a
card, a record not changing while browsing, the hand-off running the same
engine as the Eligibility page (identical states), an empty profile flagged in
the dialog, and every sidebar name landing on its own page. Rendered the real
page off-screen at 1120 px with three seeded records: 3 cards, "3 of 3
record(s) match - 2 with an open deadline", CLOSING SOON / OPEN / NO DATE
chips, and searching "germany" narrowed it to 1 of 3.

**Known limits:** matching is a substring search over stored text (honest as a
reading aid, not a linguistic search - "bachelor" finds "Bacheloropolis");
level matching depends on how the page words it, so an unusual phrase falls
through to "any level" rather than being guessed; "closing soon" is a fixed
90-day window; the eligibility hand-off reuses the record's stored values as of
the last catalog run - a page that changed since then is caught by **Re-check**,
not by Discover; saving is per record, not per search.

---

### 2026-10-21 — A26 — Phase 1: catalog + crawler (G144-G148)

**Satisfies:** G144 (sources registry), G145 (crawler), G146 (background run +
Catalog page), G147 (catalog record + `scholarship_sources`), G148 (dedup by
`canonical_key`, never overwrite a verified value). Reuses G139's tolerant
verbatim check and G143's SSRF-guarded fetch.

| Area | File(s) |
| ---- | ------- |
| Registry parsing/validation, shipped + user copy, defaults | `src/scholarpath/registry.py`, `src/scholarpath/data/sources_registry.toml` |
| Crawler: robots, sitemaps, feeds, same-site links, throttle, conditional GET, page cap | `src/scholarpath/crawler.py` |
| Conditional fetch (`fetch_resource`, 304, `Resource`) | `src/scholarpath/sources.py` |
| Feed/link helpers reused by the crawler | `src/scholarpath/discovery.py` |
| Headless run: crawl → extract → verify → save, stats, cancel | `src/scholarpath/catalog.py` |
| Catalog columns, `scholarship_sources`, migration, dedup/merge/conflicts | `src/scholarpath/storage.py` |
| Catalog page: portal list + switches, progress, error box, cancel, stored records | `src/scholarpath/ui/catalog_page.py` |
| Sidebar page at index 5, titles/index map, cancel on close | `src/scholarpath/ui/main_window.py` |
| Tests | `tests/test_sources_registry.py` (20), `tests/test_crawler.py` (31), `tests/test_catalog.py` (26), `tests/test_catalog_page.py` (9) |

Behaviour: **Catalog** in the sidebar lists the portals from the registry with a
switch each and a pages-per-portal limit. A run crawls in the background, shows
what it is reading, counts the errors, and can be cancelled between pages. Every
value is verified word-for-word against the page before it is stored; a record
is recognised by its normalised title plus the portal's domain, so a second page
fills empty fields and adds a source instead of creating a duplicate, and a
differing value is kept with the disagreement written down under
`data["conflicts"]`. The page shows the conflicts, the number of pages behind a
record, and a button that opens each page.

**Evidence:** the suite is **445 passing** in ~38 s (`pytest`), including
the crawler against a loopback server (sitemap index, RSS, robots allow/disallow,
wildcards, `Crawl-delay`, redirect final URL, 304/`If-None-Match`, private-address
refusal, HTML-only, page cap) and the run against a fake crawler + fake gateway
(created / updated / merged, conflict kept, invented values dropped, cancel,
gateway and crawl errors counted, old-database migration). Live crawl of the real
portals (no model, 2 pages each): DAAD returned its scholarships index and
overview page, Chevening returned `/scholarships/` (7 043 chars) and
`/fellowships/` with ETag and Last-Modified recorded, zero errors, and the page
cap was reported honestly.

**Live URL check (2026-10-21):** 10 portals checked with the app's own guarded
fetch; **8 shipped** — Chevening, DAAD, Fulbright, Erasmus+, MEXT (Study in
Japan), Commonwealth (CSC UK), Korea GKS (Study in Korea), Turkiye Burslari.
**2 dropped, with reason:** **CSC** (`csc.edu.cn`) answers HTTP 412 to a plain
guarded request, and **Australia Awards** (`australiaawards.gov.au`) reset the
connection / timed out. Neither is shipped pretending to work. Three entries use a
substituted start URL because the obvious one 404s: Erasmus+
`/opportunities`, MEXT `studyinjapan.go.jp/en/planning/scholarships/`,
Commonwealth `cscuk.fcdo.gov.uk/scholarships-filter-search/`; Study in Korea
serves `/en/` pages by redirecting to `/ko/`, so the registry points at `/ko/`.

**Known limits:** the shipped registry is a starting set of eight portals, not a
complete one; discovery is limited to sitemaps, feeds and same-site links (no
search engine, no JavaScript menus); only HTML is read, so PDF-only prospectuses
are skipped; `Crawl-delay` can slow a host beyond one request per second but the
app never goes faster; the end-to-end verify-and-save path was exercised with a
fake gateway only — a live run against a real model was not performed (no
provider is configured to be spent on a 50-page crawl), so the first real run is
still to be watched; `deadline_date` stays empty for ambiguous wording, which is
deliberate.

---

### 2026-10-20 — A14 — Provider anonymity (G121) + chat→profile capture (G122)

**Satisfies:** G121, G122 (owner mandates after seeing the running build leak
its model name in chat).

Built:

| Area | File(s) |
| ---- | ------- |
| Canonical reply, sub-verdict probe matcher, scrub-whole-reply guard | `src/scholarpath/identity.py` |
| System prompt on every chat request; probe interception before any model call | `src/scholarpath/ui/chat_controller.py` |
| Verbatim-verified chat fact extraction + ticked-merge | `src/scholarpath/chat_profile.py` |
| Confirmation card in the transcript ("save these to your profile?") | `src/scholarpath/ui/profile_suggestion.py` |
| Transcript wiring, profile save + panel refresh | `src/scholarpath/ui/main_window.py` |

Honesty behaviours: identity probes never reach the model; a reply that names
any vendor/model token (the token list is derived from the *running
configuration*, so changing providers changes nothing structurally) is
withheld wholesale; only rows the student keeps ticked are saved; values stay
editable; fabricated values can never survive the verbatim verifier.

**Evidence:** 34 new tests (25 identity + 9 chat-profile + 5 controller incl.
probe interception and system-prompt injection); live E2E with the real
gateway — "which model are you?" answered canonically with no disclosure,
and "my name is Rajesh Katuwala… London Metropolitan… IELTS with 7.0" produced
a confirmation card that saved exactly those three fields into the profile.

---

### 2026-10-20 — A17 — Listening ripple on the mic button (G125)

**Satisfies:** G125 (owner ask: show a listening-type ripple after clicking
the mic).

Built:

| Area | File(s) |
| ---- | ------- |
| Animated mic widget: two expanding fading rings (1.4 s loop), accent core, white glyph; 16 ms timer only while listening | `src/scholarpath/ui/mic_button.py` |
| Composer wiring: ripple starts with the capture, ends on result/failure/stop | `src/scholarpath/ui/main_window.py` |
| Ripple geometry tests (bounds, expansion, fade, wrap, half-cycle offset) | `tests/test_mic_button.py` |

Bug fixed on the way: the old start path disabled the mic for the whole
capture, so "click again to stop" was impossible; the button now stays
enabled while listening, the same click cancels ("Stopping the microphone…"
notice), and the ripple stops immediately.

Also restored in this change: image-OCR support (M4) got its `winsdk`
dependency back after the G124 engine swap dropped it — now declared as the
optional `ocr` extra in `pyproject.toml` and installed locally (`ocr_available`
True again; the previously skipped OCR test passes).

**Evidence:** 208 tests passing, no skips. E2E: click starts listening state
(timer on, stays enabled), two grabbed frames differ (animation live), frames
show visible pulse rings at 54 px; finished capture inserts text, ripple and
timer stop, review notice shows.

---

### 2026-10-21 — A25 — A packaged, audited Windows build (G138, G207)

**Satisfies:** G138 (ship as a self-contained app) and G207 (M7: security
review, testing, performance, Windows packaging).

Built:

| Area | File(s) |
| ---- | ------- |
| PyInstaller build definition (windowed app, optional OCR bundled when installed) | `packaging/scholarpath.spec` |
| One-command build that also audits the result | `packaging/build.ps1` |
| Bundle security audit (no config/database/logs/keys/secrets, runtime bundled) | `packaging/verify_bundle.py` |
| Invariants that must hold in the source tree | `tests/test_packaging.py` (4 tests) |
| `.gitignore` now keeps the spec, still ignores `dist/` and `build/` | `.gitignore` |

Behaviour: `packaging\build.ps1` builds `dist\ScholarPathAI\ScholarPathAI.exe`
and then audits the bundle, failing the build if a user config, database,
log, credential file, private key or secret-looking value is inside it. The
app itself keeps writing config, database and logs to `%APPDATA%\ScholarPath`
- never into the program folder, which is what a frozen app requires.

**Evidence:** 300 tests passing. The packaged build was launched and showed
its own window in **1.6 s**, logged to `%APPDATA%\ScholarPath\logs`, and
connected to the gateway normally. The audit scanned 520 files and reported
"no user data, no secrets, interpreter bundled (198 MB)".

**Known limits:** verified on this machine, not on a freshly installed
Windows with no Python present; the build is a folder app, not a signed
installer (`.msi` / Inno Setup is the next step); the bundle is 198 MB, which
is mostly PySide6 Essentials; the voice, search and OCR features were not
exercised through the packaged build yet, only the chat, gateway and window
start-up.

---

### 2026-10-21 — A25 — Hardening, honesty and the last features (G139-G143)

**Satisfies:** G139 (tolerant but honest verification), G140 (privacy
switches), G141 (official-domain allowlist), G142 (Re-check action) and G143
(SSRF-hardened fetching) - one commit each, with tests.

| Change | Commit | Tests |
| ------ | ------ | ----- |
| SSRF-hardened fetching (resolve, validate, re-check redirects, pin the address) | `699a6ce` | `tests/test_sources.py` (+8) |
| Normalised verbatim verification, dates by value | `7fc7527` | `tests/test_verbatim.py` (13) |
| `[privacy]` switches, gated and disclosed | `c0655b4` | `tests/test_privacy.py` (8) |
| Exact registrable-domain allowlist + `trusted_domains` | `8f66cf5` | `tests/test_official_domains.py` (9) |
| Re-check: changed pages and passed deadlines | `55bd12a` | `tests/test_recheck.py` (10) |
| README status, feature list, architecture tree | `fc7cff5` | - |

**Evidence:** 360 tests passing. The SSRF tests cover loopback, private,
link-local, metadata (AWS/Alibaba/ECS), IPv6 and IPv4-mapped addresses, a
public-looking name that resolves to a private address, a redirect to a
metadata address, and a hostile second DNS answer that must never be used.
The verification tests cover NFKC, quote and dash styles, hyphenated line
breaks, dates in five spellings, an ambiguous numeric date, and a value that
must stay rejected. The privacy tests prove no search runs while the switch
is off and that the model is told. The re-check tests cover unchanged,
changed, deadline-passed and unreachable pages.

**Known limits:** the loopback escape hatch is a test-only flag (it never
allows a private or metadata address); the official-domain rule is a
heuristic on the registrable domain and not proof of officiality; a re-check
fetches the page the record was built from, so a record whose address moved
is reported as "could not check" rather than followed; voice input, the
spoken reply and web search are now **off by default** and must be switched
on in `[privacy]`.

---

### 2026-10-21 — A24 — Saving the profile is now unmistakable (G137)

**Satisfies:** G137 (the owner clicked Save profile and "nothing happened").

Built:

| Area | File(s) |
| ---- | ------- |
| Save feedback with the time, honest failure text, guarded refresh | `src/scholarpath/ui/profile_page.py` |
| Side card re-read on every page change; each refresh step guarded and logged | `src/scholarpath/ui/main_window.py` |
| Profile-suggestion card follows the sticky auto-scroll | `src/scholarpath/ui/main_window.py` |
| Tests | `tests/test_profile_save.py` (6 tests) |

Behaviour: the confirmation under the buttons now reads "Saved locally - 75%
complete (saved at 13:28:26)", so every save visibly changes the screen; a
save that fails says "The profile could not be saved: ..." instead of
pretending; each view refresh (profile form, right-hand card, eligibility
page) is guarded and logged so one broken view cannot leave the others stale
or fail silently; and the right-hand card is re-read from the database on
every page change, so it can no longer keep saying "Not set up yet" after a
successful save.

**Evidence:** 296 tests passing. Reproduced against a copy of the real
profile database: the save wrote the values, the card showed
"Rajesh Katuwal / 75% complete - stored locally", and the new tests assert
exactly that the card is never stale and that the message always changes.

**Known limits:** the profile form has no per-field validation beyond the
model's own rules, so a value that fails validation is reported by the
completion percentage rather than blocked.

---

### 2026-10-21 — A23 — Web search in the chat (G136)

**Satisfies:** G136 (the student asked for "search scholarship in uk" and the
app said it could not search the web).

Built:

| Area | File(s) |
| ---- | ------- |
| Keyless search client, result parsing, untrusted-data block | `src/scholarpath/websearch.py` (new) |
| Search step inside a turn (model asks -> search -> answer) | `src/scholarpath/ui/chat_controller.py` |
| Search rule in the prompts (both the app prompt and the live gateway) | `src/scholarpath/identity.py`, `src/scholarpath/gateway/opencode.py` |
| "Searching the web for …" status + honest status line | `src/scholarpath/ui/main_window.py` |
| Tests | `tests/test_websearch.py` (12 tests) |

Behaviour: when a question needs live results the model replies with
`{"search": "..."}`; the app runs one keyless search (DuckDuckGo's light
HTML endpoint - no key, no account, no SDK), then asks the model again with
the results and answers from them, naming the pages it used. Results are
untrusted third-party content, capped at 6, de-duplicated, with tracking
redirects unwrapped; university, government and registered-body domains are
listed first and every result is labelled as official-looking or not. If the
search cannot run, the student gets a plain error turn instead of an answer
from memory.

**Evidence:** 290 tests passing. Live: a real search for "chevening
scholarship 2027 deadline" returned 5 results in 1.2 s, led by
chevening.org pages, and the turn flow fed them to the model as an
untrusted-data block with the URLs and the official/not-official labels.

**Known limits:** one search per turn and no follow-up searches; results are
snippets, so the model may miss detail that only the page itself carries -
the student is told to confirm on the official page, and the Scholarships page
can now read and verify that page; the provider is a single keyless endpoint
and can rate-limit or change its markup; ranking is a domain-suffix
heuristic, not proof of officialness.

---

### 2026-10-21 — A22 — Find scholarship pages on a trusted site (G134)

**Satisfies:** G134 (the Scholarships page only read URLs the student pasted).

Built:

| Area | File(s) |
| ---- | ------- |
| Link discovery: same-site scholarship/funding links from a page's own HTML | `src/scholarpath/discovery.py` (new) |
| `fetch_html` sharing the strict guardrails with `fetch_page` | `src/scholarpath/sources.py` |
| "Find pages" action + "Links published on that page" card + click-to-verify | `src/scholarpath/ui/research_page.py` |
| Tests | `tests/test_discovery.py` (14 tests) |

Behaviour: paste a university's or funding portal's scholarships page and
press **Find pages**. The app lists the scholarship and funding links that
page itself publishes - same site only, documents skipped, deduplicated,
capped at 12, with link text ranked above URL-only matches. Clicking one fills
the address box and runs the existing read-and-verify flow, so the student
still confirms every value before anything is saved.

**Evidence:** 278 tests passing. End-to-end against a local site: an index
page with five links (two scholarships, one "About us", one off-site, one PDF)
produced exactly the two scholarship links; clicking the first read the page
and returned "3 field(s) proposed, 3 verbatim on the page".

**Known limits:** this is discovery *within a site the student chose*, not an
open web search - there is still no search API, so the app cannot find
scholarship portals on its own; links behind JavaScript menus are not seen;
one page is scanned per press (no crawling of linked index pages).

---

### 2026-10-21 — A21 — Neural voice that is actually audible (G133)

**Satisfies:** G133 (the model replied, the bar said "Speaking…", and no
sound came out).

Built:

| Area | File(s) |
| ---- | ------- |
| Neural MP3 decoded to WAV and played through winmm; playback guard + offline fallback | `src/scholarpath/tts.py` |
| Decoder dependency | `pyproject.toml` (`miniaudio`) |
| Tests | `tests/test_tts.py` (+3 tests) |

Behaviour: the neural audio is decoded to a WAV file and played through the
Windows audio engine - the same route the local Windows voice uses, which
the owner could hear before. If the WAV cannot be produced the MP3 is played
directly, and if the sound device does not really run the neural engine is
treated as failed so the offline voice speaks instead of silence. Every
utterance logs the route and the timing, e.g. `neural voice played .wav
(3.62s of audio in 4.09s)`.

**Evidence:** 264 tests passing. Measured: the synthesized audio is healthy
(3.62 s, peak -4.2 dBFS, RMS -22.8 dBFS) - the old MP3/MCI route was the
fault, not the audio; the new WAV route was played by Windows end to end
(3.62 s of audio in 4.09 s of wall clock).

**Known limits:** the audible confirmation is the owner's ear - the previous
route was reported silent and the new one is mechanically verified only; the
fallback voice is the rougher offline one; playback is still blocking, so
turning the mode off stops the sound a moment later.

---

### 2026-10-21 — A20 — Human-sounding replies + voice that survives failures (G131, G132)

**Satisfies:** G131 (the `**` and `--` made the conversation look machine-made)
and G132 (the model stopped speaking in live conversation after the voice
change).

Built:

| Area | File(s) |
| ---- | ------- |
| Plain-prose cleanup for the bubble, the copy button and the voice | `src/scholarpath/prose.py` (new) |
| Tone rules: plain sentences, contractions, no markdown | `src/scholarpath/identity.py`, `src/scholarpath/gateway/opencode.py` |
| App rules kept in the instruction block of the live prompt | `src/scholarpath/gateway/opencode.py` |
| Voice survives a failed reply, loop logging, worker lifetime | `src/scholarpath/ui/main_window.py` |
| Microphone really released on cancel | `src/scholarpath/voice.py` |
| Tests | `tests/test_prose.py` (10 tests), `tests/test_voice.py` (+2 tests) |

Behaviour: the model is asked to answer like a knowledgeable friend - plain
sentences, contractions, no markdown - and anything that still arrives as
markdown is cleaned before the student sees it (bold asterisks gone, `--` a
real dash, headings and rules dropped, dash bullets as dots, tables as plain
lines, links keeping their label and URL). The voice reads the same clean
text. When a model reply fails, voice mode says so out loud and keeps
listening instead of stopping, and cancelling a capture now really releases
the microphone.

**Evidence:** 261 tests passing. Live check: a markdown-heavy reply came out
of the bubble as plain prose (no `**`, `--`, `##` or table rules), and a
forced model failure produced the spoken apology with voice mode still on and
the state back at "Listening - speak now".

**Known limits:** a reply that is one long table or a long list still reads
as a list in the bubble (the wording changes, the structure stays); the tone
rules shape the model but cannot guarantee every reply is warm; the
"speaking apology" voice is the same engine as the replies.

---

### 2026-10-21 — A19 — Natural voice + sticky transcript auto-scroll (G130)

**Satisfies:** G130 (owner ask: the voice sounded robotic; the conversation
view stopped following new messages).

Built:

| Area | File(s) |
| ---- | ------- |
| Neural voice (Edge TTS, no key) with automatic offline SAPI fallback; engine reporting | `src/scholarpath/tts.py` |
| Sticky auto-scroll (threshold helper, cancellable re-pin timer) | `src/scholarpath/ui/main_window.py` |
| Engine/scroll tests | `tests/test_voice_quality.py` (5 tests) |

Behaviour: replies are spoken with the free Edge neural voice (Aria, with
Jenny/Guy as fallbacks) and played locally through `winsound`; if the neural
engine is unavailable or fails, the offline Windows voice speaks instead -
the app never goes mute - and the voice bar states which engine really
spoke. The transcript now follows new messages while the student is at the
bottom; scrolling up to read history stops the following, cancels any pending
re-pin, and scrolling back down re-arms it.

**Evidence:** 249 tests passing. Live: a real neural utterance was
synthesised and played (3.7-4.2 s, engine reported "neural"); the fallback
path was proven by breaking the neural engine (the offline voice spoke and
the engine switched to "offline"). Scroll: after eight exchanges the view
settles at the newest message; scrolling up then adding a turn leaves the
view where the student put it.

**Known limits:** the neural voice needs the internet and sends the reply
text to Microsoft's speech service; the offline fallback sounds rougher; the
voice is still turn-based (no barge-in).

---

### 2026-10-21 — A18 — Live voice agent (G126)

**Satisfies:** G126 (owner ask: a live voice agent that talks back like
ChatGPT voice).

Built:

| Area | File(s) |
| ---- | ------- |
| Spoken replies: markdown cleaning, sentence-boundary truncation, worker-thread speaker | `src/scholarpath/tts.py` |
| Voice-mode loop, voice bar (state + End), "Live voice" toggle, speak hook on assistant turns | `src/scholarpath/ui/main_window.py` |
| Styles for the voice bar and toggle | `src/scholarpath/ui/theme.py` |
| Cleaning / truncation / speaker lifecycle tests | `tests/test_tts.py` (11 tests) |
| Dependencies: `pyttsx3` + `pywin32` (Windows SAPI, offline) | `pyproject.toml` |

Behaviour: "Live voice" starts a hands-free loop - listen (STT) -> the words
become a normal chat message -> the model replies -> the reply is spoken
aloud (SAPI, offline) -> listen again. The voice bar shows the real state
(Listening / Thinking / Speaking / Nothing heard yet) and an End button that
stops the capture and the speech. Spoken text is markdown-free and URLs are
replaced by "link in the chat"; long replies are truncated at a sentence for
speech only. Three empty captures stop the mode with an honest notice; the
mode refuses to start without a live model connection or a working
microphone/speaker, always with a reason.

**Evidence:** 244 tests passing (11 new). E2E with a fake gateway: one
transcribed phrase became the user turn, the reply was spoken as "Yes. You can
apply for the Chevening Scholarship. Check the official page for dates."
(markdown and URL removed), the loop returned to listening, and stopping
restored the idle state with the mic usable again. Real SAPI utterance
measured at 2.2 s (engine start + speech) on this machine.

**Known limits:** turn-based (not full duplex) - the app listens after each
reply, so it cannot be interrupted mid-sentence; English (`en-US`) input;
speech output is the local SAPI voice, quality is the OS default.

---

### 2026-10-20 - A16 - Voice engine swapped to SpeechRecognition (G124)

**Satisfies:** G124 (owner decision after seeing the Windows toggle requirement);
supersedes the engine choice in A15, keeps G123's interaction.

Built:

| Area | File(s) |
| ---- | ------- |
| Mic capture + transcription via `SpeechRecognition`/PyAudio, cancel, honest errors | `src/scholarpath/voice.py` (rewritten) |
| Tooltip/notices naming the library and the Google speech service | `src/scholarpath/ui/main_window.py` |
| Dependencies: `SpeechRecognition` + `PyAudio` replace `winsdk` | `pyproject.toml` |
| Library-stubbed tests: availability, success, no-speech, crash, cancel | `tests/test_voice.py` (10 tests) |

Behaviour: click mic -> records from the default microphone (no Windows toggle,
no model download) -> end-silence or a second click ends capture -> the free
web speech engine returns text that lands editable in the composer. Failures
surface as informative notices ("Nothing was heard...", "No microphone...",
"The speech service could not be reached..."), never as crashes or silence.
Fixed during verification: a voice notice no longer uses the red error style,
and a stale failure notice is cleared when the next capture succeeds.

**Evidence:** 207 tests passing. Live E2E through the app: the real microphone
capture ran the full 15 s no-speech path and showed the honest notice with the
mic usable again; the stubbed success path inserted "check if I am eligible for
Chevening" and the review notice. The real transcription service was proven
with the library's human-speech sample ("1 2"); synthetic Windows TTS audio is
rejected by the service (not user audio).

**Known limits:** English (`en-US`) dictation; needs internet for the free web
speech engine; accuracy is the service's, reported verbatim (no auto-send).

---

### 2026-10-20 — A15 — Voice input in chat (G123)

**Satisfies:** G123 (owner mandate: give prompts or talk to the model by voice).

Built:

| Area | File(s) |
| ---- | ------- |
| Dictation capture, cancel, availability probe, honest status mapping | `src/scholarpath/voice.py` |
| Mic button in the composer, press-to-talk toggle, status-strip notices | `src/scholarpath/ui/main_window.py` (`_toggle_voice`, `_VoiceWorker`) |
| Windows toggle read-only probe (`OnlineSpeechPrivacy\HasAccepted`) | `src/scholarpath/voice.py` (`_online_speech_enabled`) |
| Engine dependency, Windows-only marker | `pyproject.toml` (`winsdk` + comment) |

Behaviour: click mic → Windows Speech dictation (press-to-talk) → recognized
words land **editable** in the composer for review before Enter; second click
force-stops; every Windows failure (toggle off, mic unavailable, timeouts,
audio quality, language pack) becomes a plain-language notice, never silent.
With the Windows "Online speech recognition" toggle off (its state on this
machine), the click shows the exact settings path and needs no app restart.
UI copy names Windows speech recognition (online) — the audio goes to
Microsoft's Windows speech service, the chat model receives only the final
text (goals.md §19i, corrected during this work after the first draft wrongly
claimed fully on-device recognition).

**Evidence:** 7 tests in `tests/test_voice.py`; suite total 204 passing. UI
E2E: toggle-off click shows the actionable notice; toggle-on (mocked) click
inserts the transcript and the status strip confirms the review step. Real
recognition awaits the owner flipping the Windows toggle (audio to Windows
speech service) — the only remaining manual step.

**Known limits:** English-language dictation on Windows speech; requires the
Windows toggle; accuracy is Microsoft's recognizer, reported verbatim (no
cleanup or auto-send by design).

---

### 2026-10-20 — A13 — Milestone 6 complete: saved opportunities, comparison, checklists, MCP

**Satisfies:** G206, G109 (read-only default, untrusted tool output), G108
(saved list + settings page), G110 (persistence, deletion cascade, no secrets).

Built:

| Area | File(s) |
| ---- | ------- |
| Stdlib MCP client: initialize / tools/list / tools/call, read-only guard, size caps | `src/scholarpath/mcp/client.py` |
| `[mcp]` config section: opt-in, read-only default, unique names, no secrets | `src/scholarpath/config.py`, `config.example.toml` |
| `saved_opportunity` + `checklist_item` tables, CRUD, cascade on delete | `src/scholarpath/storage.py` |
| Checklist drafting from verbatim values only | `src/scholarpath/research.py` (`draft_checklist`) |
| Saved page: list, compare selection, side-by-side grid, per-record checklists | `src/scholarpath/ui/saved_page.py` |
| Settings page: honest model/data/MCP status, "Check tools" probe | `src/scholarpath/ui/settings_page.py` |
| Save ★ toggles on Eligibility + Scholarship record cards | `src/scholarpath/ui/eligibility_page.py`, `research_page.py` |
| Sidebar Saved Opportunities + Settings live; page-aware copy | `src/scholarpath/ui/main_window.py` |

Honesty behaviours: nothing auto-saves; comparison is labelled "a reading aid,
not a ranking"; checklists contain only verbatim-derived steps plus one fixed
static line; MCP servers never start unless config enables them, tools that
don't advertise `readOnlyHint` are refused while `read_only = true`, and tool
output is size-capped data that is never executed or quoted into prompts.

**Evidence:** 46 new tests (10 MCP with a scripted stdio server over a real
pipe, 5 config, 5 storage persistence/cascade, 4 checklist drafting); suite
**197 passing**; UI E2E — save toggle on two records persisted, checklist
generated and persisted through regeneration (ticks survive), 2-record
comparison grid rendered, Settings honest off-state rendered.

---
### 2026-10-20 — A12 — Milestone 5 complete: deterministic eligibility + ranked reports

**Satisfies:** G205, G107 (all bullet points except funding-type ranking, deferred
with reason); honours the "never call a student eligible with unknowns" rule.

Built:

| Area | File(s) |
| ---- | ------- |
| Rule-based checks: nationality, degree, language, academic GPA, deadline | `src/scholarpath/eligibility.py` |
| States + explanations + page evidence per requirement (`RequirementResult`) | `src/scholarpath/eligibility.py` |
| Honest verdicts (conflicts / potential only / no conflicts found) | `src/scholarpath/eligibility.py` |
| Deterministic ranking key (conflicts → open checks → satisfied → title/id) | `src/scholarpath/eligibility.py` |
| Eligibility page: profile summary, ranked report cards, evidence, source link | `src/scholarpath/ui/eligibility_page.py` |
| State chips (CapLive/CapGrey/CapAmber/CapFail) + link button styles | `src/scholarpath/ui/theme.py` |
| Sidebar "Eligibility" + live "Check Eligibility" tile, page-aware copy | `src/scholarpath/ui/main_window.py` |

Key honesty behaviours:

- No model calls anywhere in the engine — pure deterministic Python.
- GPA compared **only** when the page states its scale and it matches the
  profile's; a scale difference is reported, never silently converted.
- Only unambiguous month-name deadlines parsed; `01/02/2026`-style ambiguity
  is "needs checking", never guessed.
- The verdict strings never contain "eligible" and never show a percentage.
- Long page evidence is truncated in the UI (200 chars) to keep citations
  readable (the 150-country Chevening list case).

**Evidence:** 29 new engine tests; full suite **134 pytest tests passing**
(~11 s); live E2E against the real M4 Chevening record — nationality satisfied
("The page lists Nepal"), degree satisfied ("one-year master's degrees"),
language/academic/deadline honestly unknown, verdict "Potential only — 3
requirement(s) need checking"; themed full-window screenshot verified.

---

### 2026-10-20 — A11 — Milestone 4 complete: official scholarship page verification

**Satisfies:** G204, G106 (source hierarchy principle: only official pages enter
the record), G109 (untrusted-input boundary), G110 (privacy, local records)

Built:

| Area | File(s) |
| ---- | ------- |
| Guarded page fetch (scheme/type/size/redirects, sha256 + timestamps) | `src/scholarpath/sources.py` |
| 16-field schema, verbatim verification, draft/status | `src/scholarpath/research.py` |
| Parameterized JSON parse (per-pipeline field sets) | `src/scholarpath/extraction.py` |
| `scholarship` table + CRUD | `src/scholarpath/storage.py` |
| Research page (URL → fetch → confirm rows → save/delete) | `src/scholarpath/ui/research_page.py` |
| Shared confirm-row widget (documents + research) | `src/scholarpath/ui/confirm_row.py` |
| Sidebar + tile wiring, page-aware copy | `src/scholarpath/ui/main_window.py` |
| Tests | `tests/test_sources.py`, `tests/test_research.py` |

Verified, not assumed:

- `pytest` → **105 passed** (10 sources + 11 research new; fake HTTP server
  covers scheme refusal, content-type refusal, 404, redirect final-URL,
  truncation hash, unloadable host, empty page; draft tests cover kept-verbatim
  vs unknown split, prompt boundary markers, storage round-trip).
- **Live end-to-end**: fetched `https://www.chevening.org/scholarships/`
  (7,043 chars, sha256 recorded); the configured gateway proposed 6 fields —
  title, institution (FCDO), host country, eligible nationalities, degree
  levels ("one-year master's degrees"), funding coverage ("fully-funded") —
  every one asserted verbatim in the page text, then saved as a
  `page-verified` record with URL + retrieval timestamp + page hash.
- "No automatic search" is stated in the page lead, tile tooltip and status
  strip — the honest discovery boundary is part of the UI, not a footnote.
- Fixed during review: `parse_model_json` was hardwired to profile fields (now
  parameterized); a BOM slipped into two files through a PowerShell rewrite
  (caught by syntax check, removed).

Known limits:

- The Chevening page lists no deadline etc. — the model correctly left them
  null, so the saved record has no unknowns flagged for them; richer pages will
  exercise the unknown path more (unit-tested).
- `eligible_nationalities` holds the page's country list verbatim (150+ names);
  no normalisation until a documented conversion policy exists (G105).
- No per-field provenance storage (which page text span each value came from) —
  the sha256 + full field-level verbatim check is the current evidence.

---

### 2026-10-20 — A10 — Milestone 3 complete: profile + document ingestion + confirmed extraction

**Satisfies:** G203, G105 (profile + document support; confirmation), G103, G110 (local-first privacy)

Built:

| Area | File(s) |
| ---- | ------- |
| SQLite storage (documents + profile, thread-safe) | `src/scholarpath/storage.py` |
| Strict profile model + verified merge + completion | `src/scholarpath/profiles.py` |
| PDF / text / image ingestion with Windows OCR | `src/scholarpath/documents.py` |
| Gateway prompt, JSON parsing, verbatim verification | `src/scholarpath/extraction.py` |
| Profile form page (local-only) | `src/scholarpath/ui/profile_page.py` |
| Upload → propose → confirm → apply page | `src/scholarpath/ui/documents_page.py` |
| Stacked pages, sidebar wiring, profile mini-card | `src/scholarpath/ui/main_window.py` |
| Tests | `tests/test_extraction.py`, `tests/test_storage.py` |

Verified, not assumed:

- `pytest` → **84 passed** (16 storage + 20 extraction new; all prior green).
- **Live end-to-end**: a synthetic marksheet PNG read with Windows OCR (93 chars),
  the configured gateway proposed student name, degree level, graduation year and
  GPA — all four verified verbatim against the OCR text, merged (33% complete),
  round-tripped through SQLite. (OCR misread "GPA" as "CPA"; the model's proposed
  `3.62 / 4.00` is still literally in the source, so the verification stays honest.)
- **UI confirm path**: ticking only 2 of 4 rows and calling the page's apply
  handler saved exactly those two fields; unticked GPA/degree stayed empty.
- **Profile form round-trip**: a free-text degree title ("Bachelor of Science")
  survives opening the form and re-saving; the five known options still store
  their stable keys ("master" etc.). A wipe bug (the old literal-only dropdown
  silently cleared extracted titles on save) was caught this way and fixed.
- Fixed during review: documents scroll area painted black (missing viewport QSS),
  a detached placeholder label left a ghost card, the Apply handler initially did
  not merge — all corrected and re-verified with off-screen renders.
- Real-window renders inspected: profile page (form + status strip page-aware) and
  documents page (provenance text, source preview, green ✓ markers, warning rows).

Known limits:

- Extraction runs on the configured chat model; no dedicated vision/extract model
  chosen yet. Multi-page PDFs work but heavy documents are untested.
- No document deletion confirmation dialog; the record (and its confirmed values
  already merged into the profile) cannot be retracted by deleting the document.
- Research and eligibility are untouched — M4/M5 per plan.

---

### 2026-10-20 — A9 · Provider-neutral UI + "Soon" badges (design pass)

**Satisfies:** G120 (copy pass), G108 (UX clarity), G110 (privacy principle)

- User request: students must not see the model provider in the UI, and the
  M3/M4/M6 sidebar badges were unreadable jargon.
- Changes (`main_window.py`, `theme.py`, `chat_controller.py`):
  - status chip is now a small "● Live" (transparent, green text) or
    "● Offline"; the previous filled chip was also stretched to the full
    top-bar height by the layout — fixed with `Qt.AlignVCenter` sizing,
  - status strip: `chat: live|offline` instead of `gateway: <provider>`,
  - subtitle/hint copy no longer names OpenCode,
  - assistant turn header is just "SCHOLARPATH" (served model stays in logs; a
    `chat_mode` property on `ChatController` carries the neutral label),
  - all Mx badges → "Soon" with tooltips "Coming in Milestone N …".
- Verified by rendering the **real window** off-screen with real fonts
  (Qt `WA_DontShowOnScreen` + `grab()`): empty state and a live two-turn
  conversation with a real model reply — provider never appears. `pytest`
  **57 passing**; fresh app launch shows the new UI.

Known limit: README and config docs still name OpenCode — intentional: config
and documentation are technical surfaces, not the student UI.

---

### 2026-10-20 — A8 · Milestone 2 complete — OpenCode gateway adapter

**Satisfies:** G202, G104 (partially — model registry + task routing), G103

- `src/scholarpath/gateway/opencode.py` — the real adapter against the local
  OpenCode background service, protocol verified beforehand:
  - discovery: registration file `~/.local/state/opencode/service.json`
    (`XDG_STATE_HOME` / `LOCALAPPDATA` / explicit override),
  - auth: `Basic base64("opencode:<password>")`,
  - one completion = one session: `POST /api/session` → `POST .../prompt` →
    `POST /api/experimental/session/.../wait` → `GET .../message` (newest
    assistant message after the prompt timestamp) → `DELETE` best-effort,
  - honest failures: `GatewayNotConfigured` (no registration / bad password),
    `GatewayRateLimited` (429), `GatewayUnavailable` (503 / unreachable),
    `GatewayTimeout` (deadline or no assistant reply), `GatewayProtocolError`
    (unknown shape / unparseable reply).
- `src/scholarpath/gateway/registry.py` — `ModelRegistry`/`ModelEntry` loaded
  from `GET /api/model`, with deterministic task routing: chat (configured then
  first enabled), classify (cheapest), extract (vision-capable then largest
  context), research (tool-capable then largest context).
- `src/scholarpath/config.py` + `config.example.toml` — new `[gateway]`
  `base_url` / `service_file` / `location_dir` (empty = auto-discovery);
  `base_url` requires the password via `OPENCODE_SERVICE_PASSWORD`. No secrets
  in source control.
- `src/scholarpath/ui/` — status pill turns green "Live · opencode" with the
  subtitle "Model replies are live … research still to come"; stub stays honest
  "Offline · stub".
- Factory dispatches `provider = "opencode"` — the M1 "arrives in Milestone 2"
  exit-code path is replaced by the real adapter.

Verified, not assumed:

- Fake OpenCode server on loopback: full session round-trip (auth checked,
  system rules + history in the prompt, session deleted exactly once), and
  every error class mapped without crashing (wrong password, 429, 503, 404,
  500, corrupt JSON, unreachable port, wait timeout, missing assistant reply).
- Live check against the real service: `python -c … complete(...)` → model
  replied **"gateway live"**, `opencode/beam-free`, finish `stop`, usage
  recorded; catalogue read and routed.
- `pytest` → **56 passed** (25 original unchanged, 31 new).

Known limits:

- `gateway.retries` accepted but not acted on (recorded as a decision — no blind
  retry of billable completions).
- No streaming: the reply appears once, after the wait completes (~seconds on
  the free model).
- Free-tier one-shot endpoint (`/api/experimental/generate`) is refused from
  outside OpenCode; the session path is what works.

---
### 2026-10-20 — A7 · Light dashboard UI implemented + Reddit-orange recolour

**Satisfies:** G108 (partially — chat UX), G120 (new)

- Rebuilt the M1 Qt shell as a light "AI dashboard"
  (`src/scholarpath/ui/main_window.py`, `theme.py`):
  - white sidebar with real milestones (disabled items carry M3/M4/M5/M6 badges),
  - orange-gradient welcome card "Hello." with wired quick-action tiles,
  - light-blue assistant cards + orange gradient user bubbles, hover "Copy",
  - academic-profile panel showing real state ("Not set up yet", `—` values,
    0% complete — nothing invented),
  - "What works today" capability card, slim status strip with gateway/model/
    message count and elided config path,
  - `Segoe MDL2 Assets` glyphs for nav/icons (verified installed).
- Second pass (same day): user-shared Reddit-style recolour — **palette swapped
  in `theme.py` only, structure untouched**: `#FF4500`-family orange accents,
  white chrome, orange user bubble / send button, blue assistant bubble.
- Evidence: screenshots at 1440×900 empty + conversation and 1120×760 — no
  clipping, chips/tiles wrap via `FlowLayout`, `pytest` **25 passing**, app
  launches. `docs/screenshot.png` replaced with the live Reddit-colour build.
- Honesty carried over: every unbuilt feature is labelled with its milestone;
  clicking a future tile posts "Not available in this build — … arrives in
  Milestone N." Settings opens the real config folder (`QDesktopServices`).

Known limits: the earlier muted/editorial brief (`antigravityUI.md`) now describes
the *old* look — kept as historical contract, superseded by `goals.md` §19a and
`theme.py`. Suggestion chips were replaced by the four action tiles. Chat copy
still comes from the deterministic stub; nothing pretends research happened.

---

### 2026-10-20 — A6 · Stitch design prompts + rendered references

**Satisfies:** G119

- `stitch-prompt.md` — project setup prompt, three screen prompts (empty state,
  conversation + error, read-only settings), an iteration table for common drift,
  and guardrails.
- Generated in Stitch project `projects/551533196934687083` (`ScholarPath AI UI`):
  - empty state → `screens/d548bb6780ae4bcbbb7703972a44f5f0`
  - conversation + error → `screens/7714757823734a27a758c521bff36c0a`
- Committed as `docs/stitch-empty-state.png` (600×480 preview) and
  `docs/stitch-conversation.png`. Cleaned one render pass: removed an invented
  header label, a stray fourth chip, a "CONTEXT" control, latency metrics, and
  placeholder paths.

Verified: both screenshots downloaded and inspected; they match the brief's palette,
hierarchy and honesty rules (no scholarships, no fake progress).

Known limits: Stitch renders a web approximation, not Qt. Labels truncate at this
preview size, and the settings screen was prompted but not generated. The PNGs are a
visual reference — `antigravityUI.md` remains the contract.

---

### 2026-10-20 — A5 · UI hand-off brief for Antigravity

**Satisfies:** G118

- `antigravityUI.md` — self-contained brief for an external agent to rebuild the
  presentation layer without breaking the project's honesty rules.
- Contents: read-first list, exact M1 inventory (files, signals, `Turn` fields),
  8 hard constraints, design tokens (palette, type scale, spacing, radius, motion),
  layout measurements, six screens/states, copy rules, accessibility, suggested
  module split, acceptance checklist, deliverables, explicit out-of-scope list.
- Key guardrail: no fabricated scholarships, no simulated progress, no dead
  controls, no QtWebEngine/QML, no new dependencies.

Verified: file exists in the repo root; every referenced path and symbol matches
the current source (`ChatController` signals, `Turn` fields, `config_path()`,
`scholarpath.__version__`).

Known limit: it is a document, not an implementation. The UI it describes does not
exist until Antigravity (or this agent) builds and verifies it.

---

### 2026-10-20 — A4 · Public presentation + proprietary licence

**Satisfies:** G116, G117

- `LICENSE` — custom all-rights-reserved, source-available notice. Grants viewing
  and personal non-commercial evaluation only; forbids copying, modification,
  redistribution, sublicensing, and derivative works; states that contributions
  and pull requests are not accepted.
- `README.md` — rebuilt: badge row (status, Python, Qt, tests, licence),
  full-width screenshot, "why this exists" principle table, milestone status
  table, what-works / what-it-refuses-to-do split, collapsible quick start,
  configuration reference, architecture map, quality-gate table, privacy section,
  licence block, non-affiliation disclaimer.
- `docs/screenshot.png` — real capture of the running window (1550 × 1025) with a
  two-turn conversation. Not a mock-up.

Verified: screenshot rendered from the live app, image committed, README links
resolve to files that exist (`LICENSE`, `docs/screenshot.png`, `goals.md`,
`achievements.md`, `config.example.toml`).

Known limit: a licence controls legal reuse, not GitHub mechanics. A public repo
can still be forked by others; push access is controlled by collaborator
settings. Visibility ≠ writability — that is recorded in `goals.md` §16.

---

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

- G101, G102, G104, G106 (partial: per-field provenance), G108 (country
  filters), G109 (model-side tool use deferred), G111, G114 - product
  capabilities beyond the M6 pipeline.
- G106 funding-type ranking policy (funding values stay descriptive).
- G127, G128, G129 - provider chain, failover, OpenAI-compatible endpoint and
  key rotation: **code and tests landed** in commit `fe51cb0` (recovered from
  an interrupted session) and the suite is green, but no end-to-end run against
  a live provider yet, so they stay unverified until that happens.
- G133 - the neural voice is now played as a WAV through winmm instead of an
  MP3 through the Windows MCI MP3 device (which ran the clock silently on
  this machine). The code, the playback guard, the offline fallback and the
  tests are in place, but the **audible confirmation is still the owner's ear**,
  so the goal stays open until they hear it.
- Milestone G207 (M7: security review, performance, Windows packaging).

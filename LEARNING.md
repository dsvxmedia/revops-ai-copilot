# LEARNING.md: Build Log

Append-only. Each entry: what was verified/decided, why, and the date. This is where the
design plan's "open judgment calls" get resolved with real answers found during implementation.
Read `CLAUDE.md` for the current map, read this for *why things ended up the way they did*.

## 2026-07-07: Project kickoff

- Repo scaffolded: full folder structure created with stub files (`TODO(weaponx)` markers)
  per the approved plan at `/Users/djackson4/.claude/plans/i-want-to-create-inherited-puzzle.md`.
  Git repo initialized. No business logic implemented yet.
- Model id: using `claude-sonnet-5` as the default in `config.py` per current Anthropic model
  naming at the time of this build (Sonnet 5 / `claude-sonnet-5`). If this changes, verify
  against `client.models.list()` or Anthropic's docs before assuming it's still current: a
  prior planning pass flagged that reference data on model IDs is unreliable to trust blindly.
- Open items still needing verification during implementation (carried over from the plan's
  "Open Design Judgment Calls"):
  - Exact Opik tracing decorator/config API (`@opik.track` assumed: confirm against Opik's
    current docs before wiring `llm/claude_client.py`).
  - Exact Anthropic SDK structured-output mechanism to use for the 3 generation tasks
    (strict-prompt + `json.loads` is the safe fallback-compatible choice regardless of which
    SDK-native structured-output feature is current).
  - Scrapling's current API surface for a simple single-page fetch (confirm before writing
    `WebEnrichmentClient`).
  - Streamlit version installed, to confirm `pages/` numeric-prefix auto-discovery still works
    as expected vs. requiring `st.navigation`.

## 2026-07-07: Full implementation pass (weaponx build)

Environment probed at build time (this machine):
- **Python 3.14.4**. System interpreter is PEP-668 externally-managed (`pip install` refused
  without `--break-system-packages`), so a local **`.venv`** was created for the run/health
  check. `.venv` has only `streamlit` (+deps); the app's optional imports are all guarded, so
  mock mode runs fine there without `anthropic`/`scrapling`/`dotenv`.
- **Streamlit 1.59.0** installed into `.venv`. `pages/` numeric-prefix auto-discovery works as
  expected: the two pages appear without needing `st.navigation`. Health check: headless server
  answered `GET /_stcore/health` -> `ok` and `GET /` -> `200`.
- **anthropic 0.100.0** present in system Python (not needed for mock mode). No `ANTHROPIC_API_KEY`
  available, so **live Claude mode was NOT exercised end-to-end**: the live path is written
  (SDK `messages.create`, strict-JSON parse, guardrail-validate, template fallback on any error)
  but only the mock/template path is verified. Live path fails safe to templates by construction.
- **scrapling 0.4.9** IS importable in system Python; **opik is NOT installed**. Both imports are
  guarded. Opik tracing code is therefore written-but-untested (`opik.Opik().trace(...)`, wrapped
  in try/except); its absence is a silent no-op. If wiring Opik for real later, verify the exact
  trace API against current docs before trusting it.

Model id: kept the plan's default **`claude-sonnet-5`** in `config.py` (overridable via
`ANTHROPIC_MODEL`). Could not verify against `client.models.list()` without a key: flagged so a
future session confirms it before a live demo.

Deliberate scope decisions / trade-offs:
- **Scoring stays deterministic in both modes.** The plan floated a live-Claude scoring call; I
  kept scoring as rule-engine + mock-AI-keyword-heuristic in *both* modes so routing is identical
  and demo-safe regardless of key/network, and let the *3 generation tasks* be the live-LLM
  showcase. The engineered "rules vs AI disagree > 30" lead (#4) relies on this determinism.
- **Web enrichment is opt-in (`REVOPS_WEB_ENRICHMENT`, default off).** The hard constraint was
  "mock mode works with no network calls, deterministically." A default-on real fetch would break
  that, so `get_enrichment_client()` returns the mock unless the env flag is set. `WebEnrichmentClient`
  is still real (Scrapling `Fetcher.get`, robots.txt precheck, identifying UA) and falls back to
  mock on any failure. Added a `socket.setdefaulttimeout` guard around the fetch so `RobotFileParser.read()`
  (which has no native timeout) can never hang: verified an unreachable host degrades in ~0.3s.
- **Needs-Human-Review suppresses nurture auto-enrollment.** A lead flagged for human review keeps
  its computed band but is *not* auto-enrolled in a marketing campaign (would be wrong to fire-and-forget
  a record a human still needs to look at). Out-of-territory forced-Nurture *does* enroll.
- **Duplicate-company check** compares `lead.Company` against the CRM's `KNOWN_ACCOUNTS` (in
  `salesforce_client.py`) using `difflib.SequenceMatcher` on names normalized by stripping legal
  suffixes (inc/llc/corp/…). Sample lead #2 ("BrightPath Tutoring LLC") trips it against the seeded
  "BrightPath Tutoring, Inc." Exact raw-string matches are intentionally *not* flagged (that record
  *is* the account, not a hygiene dup).

Result: `python -m unittest discover tests` -> 38 tests OK; all 8 leads deterministic in mock mode.

## 2026-07-07: Visual redesign pass (post-QA, user-requested)

User feedback after clicking through the live preview: default Streamlit look plus emoji
throughout ("🧭", "🤖", "👉", "⚖️", "📊", etc.) read as unpolished/"childish" for a job-application
demo. Reviewed the available design/animation skills; the useful ones (`impeccable`,
`high-end-visual-design`, `motion-animations`, `gsap`) were already installed but
`impeccable`'s full gated workflow (`PRODUCT.md`/`DESIGN.md` context loader) isn't vendored into
this project, so its documented shared design laws were applied directly instead of forcing the
heavier setup for a single-app polish pass.

- Added `revops_copilot/ui_theme.py`: a warm tinted-neutral palette (no pure `#fff`/`#000`),
  one restrained accent (`#1C3D4A`, deep ink-teal: deliberately not the generic AI-purple or
  finance-navy cliché), a serif/sans type pairing, and muted dot+tint status badges instead of
  saturated pill badges. CSS-only fade-rise entrance animation on step panels
  (`prefers-reduced-motion` respected, only opacity/transform animated, ease-out-quint, no
  bounce: per the shared design-law bans on side-stripe borders, gradient text, etc.).
- Removed every emoji from `app.py` and both `pages/*.py` (confirmed via a full-repo regex sweep,
  zero remaining).
- Reskinned both dashboard bar charts with `st.altair_chart` (added `altair` to
  `requirements.txt` explicitly, though it ships as a Streamlit dependency anyway) instead of
  default `st.bar_chart`. **Gotcha hit:** when the chart data source is a plain list of dicts
  (`alt.Data(values=...)`, no pandas, per this project's "no pandas" rule) Altair can infer types
  for encodings with an explicit `:N`/`:Q` suffix, but a bare field name in `tooltip=[...]` throws
  `ValueError: ... type cannot be automatically inferred because the data is not specified as a
  pandas.DataFrame`. Fix: always suffix tooltip fields too, e.g. `tooltip=["Series:N", "Minutes:Q"]`.
- Fixed a copy bug surfaced during visual QA: the mock rep-brief template produced
  "is a Higher Education organization in Higher Education" when `account.Type` and `lead.Industry`
  were the same value. `generation_service._template_rep_brief` now only states the segment once
  when they match.
- Verified via gstack browser QA on localhost:8501 after the change: zero console errors on all
  3 pages, all 38 unit tests still pass, both charts render correctly with the new theme.

## 2026-07-07: Post-deploy bug fixes (button contrast, live-key test leak)

Two real bugs found after deploying and adding a real `ANTHROPIC_API_KEY` to a local `.env`
for live-mode testing:

1. **Button text unreadable (dark-on-dark).** `.stButton > button { color: SURFACE }` in
   `ui_theme.py` was being overridden by the broader `p, li, span, label, div { color: TEXT }`
   rule, because Streamlit renders a button's label inside nested `<div>`/`<p>` elements and
   that tag-selector rule has higher specificity than the inherited button color. Fixed by
   adding `.stButton > button *, [data-testid^="stBaseButton"] * { color: SURFACE !important; }`
   to force every descendant of the button, not just the button element itself.
2. **Unit tests silently made real, billed Claude API calls when a real key was present in
   `.env`.** `tests/test_guardrails_service.py::test_template_rep_brief_passes_guardrails`
   called the public `generation_service.generate_rep_brief()` dispatcher (which is correctly
   live-mode-sensitive for the real app) instead of the private `_template_rep_brief()`
   function its own name and comment implied it was testing: unlike its sibling
   `test_template_proposal_passes_its_own_guardrails`, which correctly called
   `_template_proposal()` directly. With a real key in the environment this made the test suite
   nondeterministic, 3000x slower (12.5s per call instead of instant), and quietly cost real
   API credits on every local test run. Fixed by calling `_template_rep_brief(...)` directly.
   **Gotcha also discovered while investigating:** `python -m unittest discover tests` (the
   command this repo's README/CLAUDE.md documents) treats `tests` as `top_level_dir` and imports
   test modules as loose top-level modules (`test_guardrails_service`, not
   `tests.test_guardrails_service`): so a `tests/__init__.py` env-var guard does **not**
   reliably run first under this invocation. The added `tests/__init__.py` guard is left in
   place as defense-in-depth for other invocation styles (e.g. pytest), but the real fix had to
   be at the individual-test level, not the package level.

Lesson for future test-writing in this repo: any test exercising `generation_service`'s public
`generate_*` functions must either run with no key in the environment, or call the private
`_template_*` function directly if the intent is specifically to test the deterministic
fallback path: never assume "no key in .env" is a safe invariant for tests to rely on.

**A third, more fundamental bug found while investigating the above:** `config.py`'s
`load_dotenv()` (no explicit path) uses python-dotenv's default behavior of walking **every
ancestor directory** of the current working directory looking for a file literally named
`.env`: it is not scoped to the project. On this machine, `/Users/djackson4/.env` (the
developer's home directory, a real ancestor of this project) has a personal
`ANTHROPIC_API_KEY`, so even with this project's own `.env` renamed away entirely, the app
still silently loaded that home-directory key and ran in live mode. This directly contradicts
the project's headline guarantee: "mock mode by default, no key required, fully
deterministic": for anyone (a developer, possibly even a reviewer) who has a global `~/.env`
with API keys of their own sitting around, which is a common personal setup.
Fixed in `config.py` by passing an explicit `dotenv_path` scoped to the project root
(`Path(__file__).resolve().parent.parent / ".env"`), so only *this* project's own `.env` is
ever considered: never a parent/home-directory one. Verified both directions: project `.env`
absent + home `~/.env` present -> mock mode; project `.env` present -> live mode, regardless of
what's sitting in the home directory.

## 2026-07-07: Dashboard crash: pandas/Altair thread-race (found via manual QA)

Rapid-fire clicking "Run all 8 sample leads" on the Metrics Dashboard hit a real crash:
`AttributeError: partially initialized module 'pandas' ... has no attribute 'Timestamp'
(most likely due to a circular import)`. This project deliberately never uses pandas for its
own data (plain dicts/lists throughout, per the "pragmatic, not over-engineered" brief), but
Altair's own internal `Chart.to_dict()` unconditionally does a lazy `import pandas` on every
call (to type-check values against `pd.Timestamp`), since pandas is an installed transitive
dependency of altair regardless of whether *we* import it. The very first time that lazy
import fires in the process, if it races against Streamlit's background file-watcher thread
also touching pandas for the first time, Python's import system can hand back a
partially-initialized module: a known class of bug, not something wrong in this project's
own logic, but real and reproducible under rapid reruns.

Fixed by adding an eager, explicit `import pandas` at the top of
`pages/2_Metrics_Dashboard.py` (before Altair is touched at all), forcing pandas fully into
`sys.modules` synchronously on page load and closing the race window. Added `pandas>=2.0` to
`requirements.txt` explicitly rather than relying on it silently riding in as altair's
transitive dependency. Stress-tested with 5 rapid-fire clicks of "Run all 8 sample leads"
after the fix: zero errors, 40 total runs recorded, charts render correctly throughout.

<!-- Add new entries above this line, newest at bottom is fine too: just keep dates. -->

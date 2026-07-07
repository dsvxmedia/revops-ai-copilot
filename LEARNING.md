# LEARNING.md — Build Log

Append-only. Each entry: what was verified/decided, why, and the date. This is where the
design plan's "open judgment calls" get resolved with real answers found during implementation
— read `CLAUDE.md` for the current map, read this for *why things ended up the way they did*.

## 2026-07-07 — Project kickoff

- Repo scaffolded: full folder structure created with stub files (`TODO(weaponx)` markers)
  per the approved plan at `/Users/djackson4/.claude/plans/i-want-to-create-inherited-puzzle.md`.
  Git repo initialized. No business logic implemented yet.
- Model id: using `claude-sonnet-5` as the default in `config.py` per current Anthropic model
  naming at the time of this build (Sonnet 5 / `claude-sonnet-5`). If this changes, verify
  against `client.models.list()` or Anthropic's docs before assuming it's still current — a
  prior planning pass flagged that reference data on model IDs is unreliable to trust blindly.
- Open items still needing verification during implementation (carried over from the plan's
  "Open Design Judgment Calls"):
  - Exact Opik tracing decorator/config API (`@opik.track` assumed — confirm against Opik's
    current docs before wiring `llm/claude_client.py`).
  - Exact Anthropic SDK structured-output mechanism to use for the 3 generation tasks
    (strict-prompt + `json.loads` is the safe fallback-compatible choice regardless of which
    SDK-native structured-output feature is current).
  - Scrapling's current API surface for a simple single-page fetch (confirm before writing
    `WebEnrichmentClient`).
  - Streamlit version installed, to confirm `pages/` numeric-prefix auto-discovery still works
    as expected vs. requiring `st.navigation`.

## 2026-07-07 — Full implementation pass (weaponx build)

Environment probed at build time (this machine):
- **Python 3.14.4**. System interpreter is PEP-668 externally-managed (`pip install` refused
  without `--break-system-packages`), so a local **`.venv`** was created for the run/health
  check. `.venv` has only `streamlit` (+deps); the app's optional imports are all guarded, so
  mock mode runs fine there without `anthropic`/`scrapling`/`dotenv`.
- **Streamlit 1.59.0** installed into `.venv`. `pages/` numeric-prefix auto-discovery works as
  expected — the two pages appear without needing `st.navigation`. Health check: headless server
  answered `GET /_stcore/health` → `ok` and `GET /` → `200`.
- **anthropic 0.100.0** present in system Python (not needed for mock mode). No `ANTHROPIC_API_KEY`
  available, so **live Claude mode was NOT exercised end-to-end** — the live path is written
  (SDK `messages.create`, strict-JSON parse, guardrail-validate, template fallback on any error)
  but only the mock/template path is verified. Live path fails safe to templates by construction.
- **scrapling 0.4.9** IS importable in system Python; **opik is NOT installed**. Both imports are
  guarded. Opik tracing code is therefore written-but-untested (`opik.Opik().trace(...)`, wrapped
  in try/except); its absence is a silent no-op. If wiring Opik for real later, verify the exact
  trace API against current docs before trusting it.

Model id: kept the plan's default **`claude-sonnet-5`** in `config.py` (overridable via
`ANTHROPIC_MODEL`). Could not verify against `client.models.list()` without a key — flagged so a
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
  (which has no native timeout) can never hang — verified an unreachable host degrades in ~0.3s.
- **Needs-Human-Review suppresses nurture auto-enrollment.** A lead flagged for human review keeps
  its computed band but is *not* auto-enrolled in a marketing campaign (would be wrong to fire-and-forget
  a record a human still needs to look at). Out-of-territory forced-Nurture *does* enroll.
- **Duplicate-company check** compares `lead.Company` against the CRM's `KNOWN_ACCOUNTS` (in
  `salesforce_client.py`) using `difflib.SequenceMatcher` on names normalized by stripping legal
  suffixes (inc/llc/corp/…). Sample lead #2 ("BrightPath Tutoring LLC") trips it against the seeded
  "BrightPath Tutoring, Inc." Exact raw-string matches are intentionally *not* flagged (that record
  *is* the account, not a hygiene dup).

Result: `python -m unittest discover tests` → 38 tests OK; all 8 leads deterministic in mock mode.

<!-- Add new entries above this line, newest at bottom is fine too — just keep dates. -->

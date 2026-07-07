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

<!-- Add new entries above this line, newest at bottom is fine too — just keep dates. -->

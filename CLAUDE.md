# CLAUDE.md — Project Memory for RevOps AI Copilot

Read this first in any new session before touching code. It's the map — the plan at
`/Users/djackson4/.claude/plans/i-want-to-create-inherited-puzzle.md` (also useful, more verbose)
is the design rationale; this file is the "where things are and how to run it" quick reference.

## What this is

A portfolio demo for a Cengage job application ("AI Automation Engineer – Sales & Marketing").
A Streamlit app simulating a Salesforce-centered "Revenue Ops AI Copilot": intake -> data
quality check -> enrichment -> scoring/routing -> (marketing campaign enrollment | rep brief ->
email -> proposal draft) -> telemetry. Runs fully offline in "mock mode" with zero API keys,
and switches to live Claude generation when `ANTHROPIC_API_KEY` is set.

## Current status

**Implemented and working end-to-end in mock mode.** Every `TODO(weaponx)` stub has been
replaced with a real implementation: models, config (incl. `SCORING_WEIGHTS`), JSON-line
logging, the 8 sample leads + content blocks + manual baseline, all three clients
(Salesforce/enrichment/marketing), all services (data quality, enrichment, scoring, routing,
generation, guardrails, content library, telemetry), the LLM layer (`prompts.py`,
`claude_client.py`), the orchestration workflow, the Streamlit app + 2 pages, the illustrative
`salesforce_native/` Apex + Flow + README, and real unit tests.

Verified (2026-07-07):
- `python -m unittest discover tests` → **38 tests, OK**.
- All 8 sample leads run deterministically in zero-key mock mode with **no network calls** and
  no fallbacks; each hits its engineered routing outcome (AE, Nurture, RFP→proposal,
  Needs-Human-Review disagreement, SDR boundary, out-of-territory override, SDR, existing-account).
- Headless Streamlit (`--server.headless true --server.port 8765`) serves: `/_stcore/health`
  returns `ok`, root returns `200`. Streamlit **1.59.0**; `pages/` numeric-prefix auto-discovery
  works with no `st.navigation` needed.

Web enrichment (Scrapling) is **opt-in** (`REVOPS_WEB_ENRICHMENT=1`) so the primary demo stays
network-free and deterministic; when enabled it does a real best-effort fetch and falls back to
mock on any failure (verified: unreachable host degrades in ~0.3s, no hang). Scoring is
deterministic (rule + mock-AI heuristic) in **both** modes — only the 3 generation tasks call
Claude live. See `LEARNING.md` for the rationale and other build-time decisions.

**Visual design (2026-07-07):** redesigned per user feedback that the default Streamlit look
plus emoji read as unpolished for a job-application demo. `revops_copilot/ui_theme.py` now
supplies a shared warm-neutral palette, one restrained ink-teal accent, serif/sans type system,
muted dot+tint status badges, and CSS-only entrance motion — call `ui_theme.inject()` at the top
of every page. Zero emoji anywhere in the codebase (verified by regex sweep). Both dashboard
charts use `st.altair_chart` (themed) instead of default `st.bar_chart`. See `LEARNING.md` for
the Altair tooltip-typing gotcha and the copy bug it surfaced and fixed.

## Folder map (what lives where)

- `app.py` — Streamlit entrypoint, the main "Run the Copilot" screen.
- `pages/1_Before_vs_After.py`, `pages/2_Metrics_Dashboard.py` — the other two Streamlit pages
  (Streamlit auto-discovers `pages/` by numeric-prefix filename ordering).
- `revops_copilot/models.py` — all dataclasses (Lead, Account, Opportunity, ScoreResult,
  RoutingDecision, RepBrief, EmailDraft, ProposalDraft, WorkflowResult).
- `revops_copilot/config.py` — env/config loading, model name default, mode-switch flags,
  tunable scoring constants.
- `revops_copilot/logging_config.py` — structured JSON-line logging setup -> `logs/events.log`.
- `revops_copilot/clients/` — external-system-shaped interfaces (all mocked or lightweight-real):
  - `salesforce_client.py` — `simple_salesforce`-shaped mock CRM client.
  - `enrichment_client.py` — `MockEnrichmentClient` + `WebEnrichmentClient` (real Scrapling
    fetch of the lead's public website, falls back to mock on any failure).
  - `marketing_platform_client.py` — Marketo/HubSpot/SFMC-shaped stubs; `enroll_in_nurture_campaign()`
    is actually invoked by the workflow for Nurture-routed leads, not dead code.
- `revops_copilot/services/` — business logic, one concern per file:
  - `data_quality_service.py` — intake hygiene (missing fields, duplicate-company detection).
  - `enrichment_service.py` — calls the enrichment client(s), merges results.
  - `scoring_service.py` — rule engine + AI-confidence blend -> `combined_score`.
  - `routing_service.py` — bands + override priority (territory, existing-customer,
    rule/AI disagreement -> Needs Human Review, RFP flag).
  - `generation_service.py` — mock-or-live generation for the 3 LLM tasks.
  - `guardrails_service.py` — validates all LLM output; on failure, falls back to templates.
  - `content_library_service.py` — tag/keyword retrieval of approved proposal content blocks.
  - `telemetry_service.py` — SQLite persistence + metrics, incl. pipeline-velocity impact.
- `revops_copilot/llm/` — `claude_client.py` (dual-mode call wrapper + optional Opik tracing),
  `prompts.py` (system prompts + required JSON shapes for the 3 generation tasks).
- `revops_copilot/orchestration/workflow.py` — `run_workflow(lead_id)`, the single place that
  calls every service in order and records step timing + telemetry. **This is the file to read
  first to understand the actual pipeline.**
- `revops_copilot/data/` — `sample_leads.json` (8 scenarios), `content_blocks.json` (approved
  proposal content), `manual_baseline.json` (illustrative manual-process time assumptions).
- `salesforce_native/` — illustrative-only Apex/Flow files, **not executed by the demo**, showing
  how this would deploy inside a real Salesforce org (Record-Triggered Flow -> Invocable Apex ->
  callout to this service -> write-back to Lead fields).
- `tests/` — stdlib `unittest`, one file per service with meaningful logic.

## Mode switches (env vars, see `.env.example`)

- `ANTHROPIC_API_KEY` unset -> mock/template mode (deterministic, no network, no cost).
  Set -> live Claude generation. Also falls back to templates automatically on any API
  error/timeout, not just a missing key.
- `ANTHROPIC_MODEL` — defaults to `claude-sonnet-5` in `config.py`.
- `OPIK_API_KEY` (or local Opik config) — enables Opik tracing on Claude calls. Absent -> app
  runs identically, just without traces. Import is guarded (try/except) so a missing `opik`
  package never breaks the app.
- Scrapling (`WebEnrichmentClient`) has no key requirement — it just needs network access and
  a `Website` field on the Account; any failure silently falls back to `MockEnrichmentClient`.

## How to run

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

`opik` and `scrapling` live in `requirements-optional.txt`, not `requirements.txt` — both are
lazily imported (see `llm/claude_client.py`, `clients/enrichment_client.py`) so the core app
never needs them. Kept separate deliberately so cloud builds (Streamlit Community Cloud, etc.)
stay fast and don't risk failing on a heavier optional dependency's install.

Tests: `python -m unittest discover tests`

## The 8 sample lead scenarios (in `sample_leads.json`) and what each proves

1. Hot enterprise university system -> Route to AE.
2. Cold SMB tutoring company -> Nurture (triggers marketing-campaign-enrollment step).
3. Formal RFP, community college district -> triggers the proposal-draft branch.
4. Ambiguous mid-market lead, engineered so rule-score and AI-confidence disagree -> Needs
   Human Review.
5. Warm mid-market K-12 district -> SDR/AE boundary case.
6. Out-of-territory lead -> disqualifier override (forced Nurture regardless of score).
7. Small corporate-training buyer -> SDR tier.
8. Existing-customer upsell -> "Route to AE (Existing Account)" special path.
One of these should also intentionally trip the duplicate-company data-quality flag.

## Conventions / house rules for this repo

- Every external integration (Claude, Opik, Scrapling, Salesforce, marketing platforms) has a
  mock/template fallback. Nothing should hard-crash the demo if a key or package is missing —
  that's not optional polish, it's the actual guardrail/fallback story the JD asks for.
- No `pandas`, no `pydantic` — stdlib `dataclasses` + explicit validation functions, per the
  "pragmatic, not over-engineered" brief.
- Manual-baseline timings and the pipeline-velocity model are explicitly illustrative
  assumptions — say so in the README and in the UI, never present them as measured data.
- `salesforce_native/` files are illustrative only. Don't wire them into the runtime app.

## Where to look next

Full design rationale, open judgment calls, and verification checklist:
`/Users/djackson4/.claude/plans/i-want-to-create-inherited-puzzle.md`. Concrete facts verified
during implementation (exact model id, exact Opik API, etc.) belong in `LEARNING.md`, not here.

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

**Scaffolding only.** All `.py`/`.json`/`.cls`/`.xml` files currently contain stub docstrings
marked `TODO(weaponx)` pointing at the relevant plan section. No business logic has been
implemented yet. The weaponx build loop implements these next, in the dependency order below.
**Update this section as modules land** — don't leave it stale.

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

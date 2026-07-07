# Changelog

Illustrative of how ongoing weekly iteration would be tracked and communicated to
stakeholders — framed as the JD's "ships weekly improvements" competency in practice, not a
literal fabricated history. See README for the honesty note on this.

## Week 1 — Foundation
- Stood up the folder structure, data model, and mock Salesforce/enrichment/marketing
  interfaces.
- Built the rule-based scoring and routing engine with tunable, named weight constants.

## Week 2 — Guardrails & Reliability
- Added guardrail validation on all LLM output (schema checks, fabrication guard on proposal
  pricing, PII/profanity scans) with automatic fallback to deterministic templates.
- Added the mock/live dual-mode switch so the demo never depends on a live API key or network
  access to run.

## Week 3 — Revenue Framing (stakeholder feedback)
- Added the pipeline-velocity impact metric to the dashboard after noting that raw
  "cycle time saved" wasn't resonating with revenue-side stakeholders as much as a
  pipeline-velocity/$ framing would.
- Closed the loop between routing and marketing automation: Nurture-routed leads are now
  actually enrolled in a (mocked) nurture campaign instead of routing being a dead end.

## Week 4 — Salesforce-Native Credibility
- Added `salesforce_native/` illustrative Apex/Flow files documenting the production
  deployment path (Record-Triggered Flow -> Invocable Apex -> callout -> Lead write-back).
- Added the data-quality/intake-hygiene check (missing-field flags, duplicate-company
  detection) ahead of enrichment.

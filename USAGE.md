# How to Use RevOps AI Copilot

A plain-language guide to actually using this demo, whether you're clicking through the
[live deployed version](https://revops-ai-copilot.streamlit.app) or running it on your own
machine. For "how do I install/run this," see the [README](README.md#setup--run) instead.
This document assumes the app is already open in front of you.

> The app also has this same guide built in. Click **How to Use** in the sidebar of the
> running app for an interactive version with live examples.

## Two ways to use this

### Option A: just click the live link (recommended, zero setup)

Open **https://revops-ai-copilot.streamlit.app** in any browser. No account, no login, no
install. It's running in mock/template mode by default: free, instant, fully deterministic.

Note: free-tier hosting sleeps after inactivity. If nobody's visited in a while, the first
load can take 10-20 seconds to wake up. That's normal, not a bug.

### Option B: run it on your own machine

```bash
git clone https://github.com/dsvxmedia/revops-ai-copilot.git
cd revops-ai-copilot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Same experience as the live link, just local.

## The 60-second quick start

1. On the main page (labeled **app** in the sidebar), open the **Sample lead** dropdown.
2. Pick any of the 8 scenarios. "1. Hot Enterprise" is the cleanest first example.
3. Click **Run Copilot**.
4. Watch the pipeline render step by step. Click any step's header to expand it and see detail.
5. When it finishes, try the **Before vs After** and **Metrics Dashboard** pages in the sidebar.

That's the whole demo. Everything below is optional depth.

## What you're actually looking at

This simulates a Salesforce-centered "Revenue Ops AI Copilot": an inbound lead or RFP request
comes in, and the system automates the busywork that would otherwise eat a sales rep's or
RevOps analyst's morning. It checks the record for data-quality problems, enriches it with
firmographic context, scores and routes it, drafts a rep brief and follow-up email, and, for
formal RFPs, drafts a proposal from pre-approved content. Every run is logged so the Metrics
Dashboard can show the aggregate business impact across runs.

### Mock mode vs. Live mode

There's a badge in the top-right of the main page that always tells you which mode you're in:

- **Mock / Template Mode** (the default, no API key needed): every output comes from
  deterministic, rule-based logic. Same input always produces the same output. Free, instant,
  no network calls.
- **Live Claude Mode** (only if an `ANTHROPIC_API_KEY` is configured): the rep brief,
  follow-up email, and proposal draft are generated live by Claude instead of a template.
  Scoring and routing stay deterministic in both modes, so the routing outcome for a given
  scenario never changes regardless of mode.

## The nine pipeline steps, explained

| Step | What it does |
|---|---|
| 1. Lead Intake | Shows the raw incoming record: company, contact, source, territory, as it would appear freshly created in a CRM. |
| 2. Data Quality Check | Flags missing critical fields and checks for likely duplicate-company records (e.g. "Acme Inc" vs. "Acme, Incorporated") before anything downstream trusts the data. |
| 3. Enrichment | Adds firmographic context, industry, employee count, current tech stack, from a mock provider (or a real lightweight web lookup if enabled). |
| 4. Scoring & Routing | Blends a transparent rule-based score with an AI read of the lead's free-text notes, then routes to AE, SDR, Nurture, or flags for human review. |
| 5. Marketing Campaign Enrollment | *(Nurture-routed leads only)* Shows the simulated enrollment into a marketing-platform nurture campaign, closing the sales-to-marketing loop instead of leaving the lead stranded. |
| 6. Rep Brief | Account summary, key buying signals, likely objections with suggested responses, and a recommended next action. |
| 7. Follow-up Email | A draft outreach email, toned to match the routing outcome. |
| 8. Proposal / RFP Draft | *(RFP requests only)* A draft proposal assembled strictly from pre-approved content blocks, never freely invented pricing, always flagged for human review before it could be sent. |
| 9. Telemetry Recorded | Records this run's cycle time against an illustrative manual-process baseline, feeding the aggregate dashboard. |

Step numbers occasionally skip (e.g. straight from 4 to 6), and that's expected. Steps 5 and 8
are conditional and only render for the scenarios they apply to.

## Understanding routing outcomes

| Badge | Meaning |
|---|---|
| **Route to AE** | High-scoring lead, ready for an Account Executive to engage directly. |
| **Route to SDR** | Mid-scoring lead, needs SDR discovery/qualification first. |
| **Route to Nurture** | Lower-scoring or early-stage lead, enrolled in a nurture campaign instead of a live rep touch. |
| **Needs Human Review** | The rule-based score and the AI's read of the lead disagreed by more than the configured threshold. This is a guardrail, not a failure: a human makes the final call rather than the system guessing. |

## The 8 sample scenarios

Each one is deliberately built to demonstrate a specific behavior, not chosen at random:

1. **Hot Enterprise, State University System**: clean high-score path, routes to AE.
2. **Cold SMB, Tutoring Company**: low-score path to Nurture, and trips the duplicate-company data-quality flag.
3. **Formal RFP, Community College District**: triggers the proposal-draft branch and the human-review gate.
4. **Ambiguous Mid-Market**: rule score and AI confidence deliberately disagree, forcing Needs Human Review.
5. **Warm Mid-Market, K-12 District**: a boundary case between SDR and AE routing.
6. **Out-of-Territory**: a disqualifying rule overrides an otherwise decent score.
7. **Small Corporate-Training Buyer**: a straightforward SDR-tier lead.
8. **Existing-Customer Upsell**: a special routing path for accounts that are already customers.

## The other two pages

**Before vs After**: pick any scenario and see a side-by-side comparison of the manual process
a rep would follow today versus what the copilot just did automatically, plus the qualitative
reasons this matters beyond raw time saved (consistency, always-on coverage, auditability).

**Metrics Dashboard**: aggregate telemetry across every run you've triggered, including total
runs, automation success rate, average time saved, percentage needing human review, and an
illustrative pipeline-velocity model translating faster response time into revenue language.
Click **Run all 8 sample leads** here to populate it quickly with one click.

## FAQ

**Is any of this real company data?**
No. All 8 leads are fictional, purpose-built sample data. Salesforce, the marketing platforms,
and firmographic enrichment are mocked interfaces. See the README's "Swappable for production"
section for how each would connect to a real system.

**Why does the proposal always say "Needs Human Review"?**
By design, unconditionally, in the code itself, regardless of how confident the generation
was. This reflects how proposal and pricing content should actually be gated in a real
deployment, not a limitation of the demo.

**Can I run my own custom lead instead of the 8 samples?**
Not through this UI. The 8 samples are intentionally fixed so every run is reproducible and
demonstrates a known behavior. `run_workflow(lead_id)` in
`revops_copilot/orchestration/workflow.py` is where you'd extend this to accept arbitrary leads.

**Something looks broken, or a chart didn't render.**
Refresh the page first: Streamlit occasionally needs a rerun after rapid clicking. If it
persists, check `LEARNING.md` in the repo. Several real bugs found during development, and
their fixes, are documented there in detail.

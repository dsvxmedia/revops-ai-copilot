# Build Process: Plan to Production

A detailed account of how this project was actually built, start to finish: the planning, the
decisions, the tooling, and every real bug found along the way. Written for anyone (technical
or not) curious about the engineering process behind this demo, not just the end result.

## Summary timeline

| Phase | What happened |
|---|---|
| 1. Brainstorming and scoping | Clarified tech-stack decisions before writing any code |
| 2. Planning | Wrote a detailed implementation plan, then reviewed it for gaps against the job description |
| 3. Scaffolding | Created the full folder structure and project memory files before any business logic |
| 4. Implementation (weaponx loop) | Built every module via a generate, independently verify, and persist loop |
| 5. Live browser QA | Clicked through the actual running app in a real browser, not just unit tests |
| 6. Merge and first deploy prep | Merged the feature branch, split optional dependencies out for reliable cloud builds |
| 7. Visual redesign | Reviewed and applied a professional design system; removed all emoji and default styling |
| 8. Going live | Created the public GitHub repo, deployed to Streamlit Community Cloud, wired up a real API key |
| 9. Post-deploy bug hunt | Found and fixed four real, non-obvious bugs surfaced only by actually using the deployed app |
| 10. Documentation pass | This document, the in-app guide, and the external usage guide |

## Phase 1: Brainstorming and scoping

Before any code was written, four concrete decisions were locked in explicitly, not assumed:

1. **UI framework**: Streamlit, local-first. Chosen over a Next.js/React rebuild because the
   JD is Python-first and the actual value being demonstrated is the automation logic, not
   frontend engineering. This was a deliberate trade-off, revisited later in Phase 7 when it
   started limiting visual polish.
2. **LLM provider**: Anthropic Claude only, no multi-provider abstraction, since only one
   provider was actually going to be demoed.
3. **API key mode**: mock-first. The app had to run fully and deterministically with **zero**
   API key before a single line of generation code was written. This constraint shaped almost
   every service that came after it.
4. **Salesforce depth**: a realistic mock data model, not a real org connection, since the goal
   was demonstrating integration *patterns*, not standing up real infrastructure.

## Phase 2: Planning

A full implementation plan was written covering the data model, scoring and routing formulas,
the three LLM generation tasks and their guardrails, the telemetry schema, and the Streamlit
UI structure. That plan is preserved in this environment's plan history for reference.

The plan was then **deliberately re-reviewed against the actual job description**, looking for
gaps. This surfaced several additions that weren't in the first draft:

- A data-quality and intake-hygiene check (the JD specifically calls out "data quality,
  hygiene, and enrichment automation").
- Actually wiring the marketing-platform client into the routing flow for Nurture-routed leads.
  It existed as a stub but nothing called it.
- A pipeline-velocity metric on the dashboard, translating raw time saved into revenue
  language. The JD's top-billed competency is "Revenue Mindset," and "0.001 seconds" doesn't
  land the way "+20% pipeline velocity" does.
- Illustrative Apex and Flow files (`salesforce_native/`) demonstrating the production
  Salesforce integration path, since the JD weights Apex/Flow/Einstein integration heavily and
  the mock Python client alone doesn't speak to that.
- A `CHANGELOG.md` narrating the "ships weekly improvements" competency.
- Two open-source integrations reviewed and added because they genuinely strengthened
  JD-relevant capability: **Opik** for LLM call observability and tracing, and **Scrapling**
  for a real (not just mocked) lightweight web-enrichment fetch.

## Phase 3: Scaffolding

Before any business logic, the complete folder structure was created with every file as a
`TODO`-marked stub, plus fully-written project memory files:

- **`CLAUDE.md`**: the map. Folder structure, mode switches, conventions, updated continuously
  as the build progressed.
- **`LEARNING.md`**: an append-only build log of facts verified and decisions made *during*
  implementation, as opposed to planned in advance. Every real bug found later in this process
  is documented there in full technical detail.

This was committed to git before implementation began, so the scaffold itself is a clean,
reviewable checkpoint.

## Phase 4: Implementation via the weaponx loop

Rather than a single best-effort implementation pass, the build used a structured plan,
generate, verify, and persist loop:

1. **Discovery**: confirmed no prior work existed on this task, domain was code, not
   high-stakes (no protected branch, no external publish at this point).
2. **Handoff**: an isolated git worktree was created (`weaponx/revops-copilot-implementation`)
   so implementation happened on an isolated branch, never touching the working checkout
   directly.
3. **Generation**: a coding agent implemented every module in dependency order (models,
   clients, services, orchestration, UI, tests), working only inside that isolated worktree.
4. **Verification**: a *separate* evaluator agent, with no visibility into the generator's own
   reasoning, independently re-derived and checked 8 concrete claims from scratch: zero
   remaining stub code, all 38 unit tests passing, a live headless server health check, the
   exact scoring math for the engineered disagreement scenario, the duplicate-company
   detection logic, the unconditional proposal human-review gate, graceful degradation with
   both optional packages absent, and a clean git history. Verdict: **PASS**, with every claim
   independently verified rather than taken on faith.
5. **Persistence**: a structured trace record of the entire run (cost, findings, verdict) was
   written before the branch was merged.

## Phase 5: Live browser QA

Unit tests and a health check aren't the same as a human clicking through the actual app, so
the running Streamlit app was driven in a real headless browser through the full demo script:
every one of the 8 scenarios and both secondary pages, checking for console errors and visual
correctness at each step, not just whether it returned a 200 status.

## Phase 6: Merge and first deploy prep

The verified branch was merged into `main` (one real merge conflict, in `.gitignore`, resolved
by keeping both entries). Before any deployment, `opik` and `scrapling` were split out of the
main `requirements.txt` into a `requirements-optional.txt`. Both are lazily imported and never
required by the core app, but a naive cloud build would have tried to install both regardless,
risking a failed deploy over a dependency the demo doesn't actually need.

## Phase 7: Visual redesign

After an initial local preview, direct feedback was blunt: the default Streamlit look plus
emoji throughout read as unpolished for a job-application demo. This became its own scoped
effort:

- Reviewed available design-oriented tooling and applied a set of concrete design laws
  directly: a restrained warm-neutral palette with one deliberate ink-teal accent, chosen
  specifically to avoid both the generic "AI purple gradient" cliche and the generic "finance
  navy" cliche, a serif and sans type pairing, CSS-only entrance motion respecting
  `prefers-reduced-motion`, and a hard ban on decorative side-stripe borders and gradient text.
- Every emoji removed from the codebase, confirmed via a full-repo regex sweep.
- Both dashboard charts rebuilt with Altair using a matching theme instead of Streamlit's
  default blue `st.bar_chart`.
- This pass itself surfaced two real bugs, fixed on the spot: an Altair `tooltip` field-typing
  crash, and a copy bug where the rep-brief template repeated itself ("a Higher Education
  organization in Higher Education") when two fields happened to share a value.

## Phase 8: Going live

1. Created a public GitHub repository and pushed `main`.
2. Deployed to Streamlit Community Cloud, the one step requiring the account owner's own
   GitHub OAuth session, not something automatable from this side.
3. Wired up a real Anthropic API key as a Streamlit Cloud secret to enable the live-Claude path
   for anyone reviewing the deployed app, with the mock-mode path remaining the safe,
   deterministic default.

## Phase 9: Post-deploy bug hunt

Going live surfaced real, non-obvious bugs that no amount of local unit testing had caught. All
were found and fixed the same day, and are documented in full in `LEARNING.md`:

1. **Button text was unreadable (dark-on-dark).** A broad CSS text-color rule was overriding
   the button's intended light label text due to a specificity conflict. Fixed with a
   higher-specificity descendant selector.
2. **The unit test suite was silently making real, billed Claude API calls** whenever a real
   API key happened to be present in the environment. One test called the live-mode-sensitive
   public function instead of the deterministic private one its own name implied, causing a
   3000x slowdown (12.5 seconds instead of instant) and a real, unnecessary cost on every local
   test run. Fixed by calling the correct function directly.
3. **A deeper bug the previous fix led to**: `.env` loading was walking *every ancestor
   directory* looking for a file named `.env`, including the developer's home directory. That
   meant a personal global `~/.env` with unrelated API keys could silently override this
   project's "mock mode by default, no key required" guarantee. Fixed by scoping the `.env`
   load explicitly to the project's own root.
4. **A real crash on the Metrics Dashboard**: Altair's internal chart serialization always does
   its own lazy `import pandas` on every render, regardless of this project never using pandas
   for its own logic, and that import racing against Streamlit's background file-watcher
   thread on its very first execution in the process could hand back a partially-initialized
   module and crash the page. Reproduced reliably via rapid-fire button clicks, fixed with an
   eager, explicit `import pandas` before Altair is touched, and stress-tested afterward to
   confirm it held up.

## Phase 10: Documentation pass

This document, the in-app **How to Use** page (click it in the running app's sidebar), and
[`USAGE.md`](USAGE.md) were all written last, once the app's actual behavior was fully known
and verified. They describe what was truly built and tested, not what was originally planned.

## What this process demonstrates

Beyond the demo's own subject matter (AI-driven RevOps automation), the process itself is the
other half of the pitch. It's a plan that gets checked against real requirements rather than
executed blindly, verification that's independent rather than self-reported, and bugs that get
found by actually using the thing, not just running its test suite, then get root-caused and
documented instead of patched over.

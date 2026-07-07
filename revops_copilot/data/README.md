# Data files (placeholders — weaponx fills these in)

- `sample_leads.json` — the 8 scenario leads described in the plan (hot enterprise, cold SMB,
  RFP, ambiguous/human-review, warm mid-market, out-of-territory, SDR-tier, existing-customer
  upsell), including one engineered duplicate-company data-quality flag case.
- `content_blocks.json` — ~6-10 approved proposal content blocks (intro, platform overview,
  higher-ed/K-12 case studies, pricing tiers, implementation timeline, security/compliance),
  each with a stable `block_id` and `tags`.
- `manual_baseline.json` — illustrative manual-process duration assumptions per task
  (enrichment research, scoring/routing judgment, brief writing, email drafting, proposal
  drafting), explicitly labeled as assumptions in the README, not measured data.

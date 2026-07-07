# Salesforce-Native Deployment Path (illustrative, not executed)

These files are **not run by the Streamlit demo**. They document how this workflow
would ship inside a real Salesforce org, for interview credibility on Apex, Flow, and
Einstein, without pretending the demo has a live Salesforce backend.

## Production flow

```
Lead created/updated
      │
      ▼
Record-Triggered Flow  (Score_And_Route_Lead.flow-meta.xml)
      │  passes Lead fields
      ▼
Invocable Apex  (RevOpsCopilotInvocable.cls)
      │  @future(callout=true) HTTP POST via Named Credential
      ▼
RevOps Copilot service  (this Python app, containerized behind an API)
      │  returns { combined_score, routing_outcome, needs_human_review, rep_brief_summary }
      ▼
Write-back to the Lead   →  AI_Score__c, AI_Routing__c,
                            AI_Needs_Human_Review__c, AI_Rep_Brief__c
      │
      ▼
(optional) Platform Event  Lead_Scored__e  →  LWC refreshes the record UI async
```

## Key design points

- **Named Credential** (`RevOps_Copilot_API`) holds the endpoint + auth, so no
  secrets live in Apex. The callout targets `callout:RevOps_Copilot_API/v1/score`.
- **Async callout** via `@future(callout=true)` (or Queueable) keeps the trigger
  context legal: callouts can't run before pending DML in a synchronous trigger.
- **Graceful degrade**: a non-200 or exception is logged and the Lead is simply
  left for manual handling, the same fallback philosophy as the Python service.
- **Custom fields** required in the org: `AI_Score__c` (Number), `AI_Routing__c`
  (Text), `AI_Needs_Human_Review__c` (Checkbox), `AI_Rep_Brief__c` (Long Text),
  and `RequestType__c` (Picklist: Inbound Lead / RFP Request).

## Where Einstein fits

In a real deployment, **Einstein Lead Scoring** could run *alongside* this custom
model: Einstein provides an out-of-the-box propensity score from historical
conversion data, while this service adds the explainable rule breakdown, the
LLM-generated rep brief/email/proposal, and the guardrail + human-review gate.
The custom `AI_Score__c` and Einstein's score can be surfaced side by side, or the
custom rules can act as an override/routing layer on top of Einstein's propensity.

## Not included on purpose

No `package.xml`, no test classes, no org deploy. These are reference artifacts,
well-formed Apex and Flow metadata, meant to be read, not `sfdx force:source:deploy`'d.

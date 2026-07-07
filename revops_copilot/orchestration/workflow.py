"""Orchestration: ``run_workflow(lead_id)`` -> ``WorkflowResult``.

Single place that calls every service in order and records per-step timing:

  intake -> data quality -> enrichment -> scoring -> routing
         -> [if Nurture: marketing enrollment]
         -> rep brief -> email -> [if RFP: proposal] -> telemetry write

Runs identically in mock and live mode; only the generation layer changes.

See plan sections "Marketing Automation Loop-Closing", "Data Quality",
"Scoring & Routing", "Generation", "Telemetry".
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Callable, List, Optional, Tuple

from .. import config
from ..clients.marketing_platform_client import MarketingPlatformClient
from ..clients.salesforce_client import MockSalesforceClient
from ..logging_config import log_event
from ..models import Lead, WorkflowResult
from ..services import (
    data_quality_service,
    enrichment_service,
    generation_service,
    routing_service,
    scoring_service,
    telemetry_service,
)


def _manual_baseline() -> dict:
    try:
        with open(config.MANUAL_BASELINE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh).get("per_task_seconds", {})
    except Exception:  # noqa: BLE001
        return {}


class _StepTimer:
    """Times each step and appends its manual-baseline cost when it runs."""

    def __init__(self):
        self.timings = {}
        self.manual_total = 0.0
        self._baseline = _manual_baseline()

    def run(self, name: str, fn: Callable):
        start = time.perf_counter()
        result = fn()
        self.timings[name] = round(time.perf_counter() - start, 4)
        self.manual_total += float(self._baseline.get(name, 0))
        return result


def run_workflow(
    lead_id: str,
    sf_client: Optional[MockSalesforceClient] = None,
    db_path: Optional[str] = None,
) -> WorkflowResult:
    """Execute the full copilot pipeline for one lead."""
    sf = sf_client or MockSalesforceClient()
    timer = _StepTimer()
    result = WorkflowResult(
        run_id=uuid.uuid4().hex,
        automation_mode=config.automation_mode(),
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

    # 1. Intake
    lead: Optional[Lead] = timer.run("intake", lambda: sf.get_lead(lead_id))
    if lead is None:
        log_event("workflow_error", lead_id=lead_id, reason="lead not found")
        raise ValueError(f"Lead not found: {lead_id}")
    result.lead = lead
    log_event("workflow_start", run_id=result.run_id, lead_id=lead_id, mode=result.automation_mode)

    # 2. Data quality
    result.data_quality = timer.run(
        "data_quality",
        lambda: data_quality_service.check_lead(lead, sf.known_account_names()),
    )

    # 3. Enrichment
    result.enrichment = timer.run("enrichment", lambda: enrichment_service.enrich_lead(lead))
    result.account = result.enrichment.account if result.enrichment else None

    # 4. Scoring (deterministic rule + AI-confidence blend)
    result.score = timer.run(
        "scoring", lambda: scoring_service.score_lead(lead, result.account)
    )

    # 5. Routing
    result.routing = timer.run("routing", lambda: routing_service.route_lead(lead, result.score))

    # 6. Marketing enrollment (Nurture-routed leads only; a lead flagged for
    #    human review is held back rather than auto-enrolled).
    if result.routing.band.startswith("Nurture") and not result.routing.needs_human_review:
        mkt = MarketingPlatformClient()
        result.marketing_enrollment = timer.run(
            "marketing_enrollment",
            lambda: mkt.enroll_in_nurture_campaign(lead, result.routing.nurture_segment),
        )

    # 7. Rep brief
    result.rep_brief = timer.run(
        "rep_brief",
        lambda: generation_service.generate_rep_brief(
            lead, result.account, result.score, result.routing, result.enrichment
        ),
    )

    # 8. Follow-up email
    result.email = timer.run(
        "email",
        lambda: generation_service.generate_email(lead, result.account, result.routing),
    )

    # 9. Proposal (RFP only) — ALWAYS forced to human review
    if result.routing.proposal_required:
        proposal = timer.run(
            "proposal", lambda: generation_service.generate_proposal(lead, result.account)
        )
        proposal.needs_human_review = True
        result.proposal = proposal

    # Aggregate timing / savings
    result.step_timings = timer.timings
    result.total_cycle_time_seconds = round(sum(timer.timings.values()), 4)
    result.manual_baseline_seconds = timer.manual_total
    result.time_saved_seconds = round(
        max(0.0, result.manual_baseline_seconds - result.total_cycle_time_seconds), 4
    )
    result.guardrail_fallback_used = any(
        [
            bool(result.rep_brief and result.rep_brief.guardrail_fallback_used),
            bool(result.email and result.email.guardrail_fallback_used),
            bool(result.proposal and result.proposal.guardrail_fallback_used),
        ]
    )

    # Write AI_* fields back to "Salesforce" (illustrative of the real callout).
    try:
        sf.update_lead(
            lead_id,
            {
                "AI_Score__c": round(result.score.combined_score),
                "AI_Routing__c": result.routing.routing_outcome,
                "AI_Needs_Human_Review__c": result.routing.needs_human_review,
            },
        )
    except Exception:  # noqa: BLE001
        pass

    # 10. Telemetry
    telemetry_service.record_run(result, db_path=db_path)
    log_event(
        "workflow_complete",
        run_id=result.run_id,
        lead_id=lead_id,
        routing=result.routing.routing_outcome,
        combined_score=round(result.score.combined_score),
        needs_human_review=result.routing.needs_human_review,
        proposal_generated=bool(result.proposal),
        guardrail_fallback_used=result.guardrail_fallback_used,
    )
    return result


def list_sample_leads(sf_client: Optional[MockSalesforceClient] = None) -> List[Tuple[str, str]]:
    """Return ``(lead_id, dropdown_label)`` pairs for the UI."""
    sf = sf_client or MockSalesforceClient()
    pairs = []
    for lead in sf.list_leads():
        label = lead.scenario_label or f"{lead.Company} ({lead.Id})"
        pairs.append((lead.Id, label))
    return pairs

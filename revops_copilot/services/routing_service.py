"""Routing: score bands + override resolution.

Override priority (highest first):
  1. out-of-territory        -> forced Nurture (disqualifier)
  2. existing customer       -> "Route to AE (Existing Account)"
  3. rule/AI disagreement>30 -> Needs Human Review
  4. RFP request             -> independent proposal_required flag (band unchanged)

See plan section "Scoring & Routing".
"""
from __future__ import annotations

from .. import config
from ..models import Lead, RoutingDecision, ScoreResult
from ..clients.marketing_platform_client import derive_segment


def _base_band(combined_score: float) -> str:
    if combined_score >= config.BAND_AE_MIN:
        return "AE"
    if combined_score >= config.BAND_SDR_MIN:
        return "SDR"
    if combined_score >= config.BAND_NURTURE_MIN:
        return "Nurture"
    return "Nurture (Low Priority)"


def _band_outcome_label(band: str) -> str:
    return {
        "AE": "Route to AE",
        "SDR": "Route to SDR",
        "Nurture": "Route to Nurture",
        "Nurture (Low Priority)": "Route to Nurture (Low Priority)",
    }.get(band, f"Route to {band}")


def is_out_of_territory(lead: Lead) -> bool:
    territory = (lead.Territory__c or "").strip()
    if not territory:
        return False
    return territory not in config.IN_TERRITORY


def route_lead(lead: Lead, score: ScoreResult) -> RoutingDecision:
    """Resolve the routing decision from the score and override rules."""
    band = _base_band(score.combined_score)
    decision = RoutingDecision(band=band, routing_outcome=_band_outcome_label(band))

    # RFP flag is independent of routing band -- set it up front.
    decision.proposal_required = lead.RequestType == "RFP Request"

    disagreement = abs(score.rule_score - score.ai_confidence_pct)

    # 1. Out-of-territory (highest priority) -> forced Nurture.
    if is_out_of_territory(lead):
        decision.band = "Nurture (Out of Territory)"
        decision.routing_outcome = "Route to Nurture (Out of Territory)"
        decision.nurture_segment = derive_segment(lead)
        decision.overrides_applied.append(
            f"Out-of-territory ({lead.Territory__c}) — forced Nurture"
        )
        return decision

    # 2. Existing customer -> AE (Existing Account).
    if lead.ExistingCustomer__c:
        decision.band = "AE"
        decision.routing_outcome = "Route to AE (Existing Account)"
        decision.overrides_applied.append("Existing customer — routed to AE")
        return decision

    # 3. Rule/AI disagreement -> Needs Human Review.
    if disagreement > config.DISAGREEMENT_THRESHOLD:
        decision.needs_human_review = True
        decision.routing_outcome = "Needs Human Review"
        decision.overrides_applied.append(
            f"Rule/AI disagreement {disagreement:.0f} pts (> {config.DISAGREEMENT_THRESHOLD:.0f}) "
            "— flagged for human review"
        )
        return decision

    # 4. Normal band. Set nurture segment for any Nurture outcome.
    if decision.band.startswith("Nurture"):
        decision.nurture_segment = derive_segment(lead)
    return decision

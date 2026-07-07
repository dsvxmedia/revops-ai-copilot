"""Dataclasses for the RevOps AI Copilot domain model.

Field names mirror real Salesforce conventions (e.g. ``NumberOfEmployees``,
``Budget_Confirmed__c``) for interview credibility. Plain stdlib ``dataclasses``
only -- no pydantic -- per the "pragmatic, not over-engineered" house rule.

See plan section "Data Model".
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _filter_known(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the keys of ``data`` that are declared fields on ``cls``.

    Lets us build a dataclass from a JSON record that may carry extra keys
    (e.g. a nested ``Opportunity`` handled separately) without blowing up.
    """
    known = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in data.items() if k in known}


@dataclass
class Opportunity:
    """A Salesforce Opportunity nested on a Lead for active-deal scenarios."""

    Id: str = ""
    Name: str = ""
    StageName: str = ""
    Amount: float = 0.0
    CloseDate: str = ""
    Type: str = ""
    Probability: float = 0.0
    NextStep: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Opportunity":
        return cls(**_filter_known(cls, data or {}))


@dataclass
class Account:
    """A Salesforce Account, populated/augmented during enrichment."""

    Id: str = ""
    Name: str = ""
    Type: str = ""  # Higher Education | K-12 | Workforce/Corporate Training | Library/Public Sector
    AnnualRevenue: float = 0.0
    NumberOfEmployees: int = 0
    BillingState: str = ""
    BillingCountry: str = "USA"
    Website: str = ""
    ExistingCustomer: bool = False
    TechStack: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        return cls(**_filter_known(cls, data or {}))


@dataclass
class Lead:
    """A Salesforce Lead -- the primary input record to the workflow."""

    Id: str = ""
    FirstName: str = ""
    LastName: str = ""
    Company: str = ""
    Title: str = ""
    Email: str = ""
    Phone: str = ""
    LeadSource: str = ""
    Status: str = "Open - Not Contacted"
    Rating: str = ""
    Industry: str = ""
    AnnualRevenue: float = 0.0
    NumberOfEmployees: int = 0
    Description: str = ""
    CreatedDate: str = ""
    RequestType: str = "Inbound Lead"  # "Inbound Lead" | "RFP Request"
    Budget_Confirmed__c: bool = False
    Timeline__c: str = ""  # e.g. "This Quarter", "This Year", "No Timeline"
    DecisionMakerIdentified__c: bool = False
    ExistingCustomer__c: bool = False
    Territory__c: str = ""
    # Convenience label for the UI dropdown; not a real SF field.
    scenario_label: str = ""
    # Nested records (not standard flat SF fields, handled explicitly).
    opportunity: Optional[Opportunity] = None
    account_seed: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.FirstName} {self.LastName}".strip()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lead":
        lead = cls(**_filter_known(cls, data))
        opp = data.get("Opportunity") or data.get("opportunity")
        if opp:
            lead.opportunity = Opportunity.from_dict(opp)
        lead.account_seed = data.get("Account") or data.get("account_seed") or {}
        return lead


@dataclass
class DataQualityResult:
    """Output of the intake-hygiene pass."""

    flags: List[str] = field(default_factory=list)
    normalized_fields: Dict[str, str] = field(default_factory=dict)
    duplicate_of: str = ""
    passed: bool = True


@dataclass
class EnrichmentResult:
    """Merged enrichment payload plus per-field provenance for the UI."""

    account: Optional[Account] = None
    # field name -> "live web signal" | "simulated"
    field_sources: Dict[str, str] = field(default_factory=dict)
    web_signal_used: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    """Rule score + AI confidence blended into a combined score (0-100)."""

    rule_score: float = 0.0
    ai_confidence: float = 0.0  # 0.0 - 1.0
    combined_score: float = 0.0
    rule_breakdown: Dict[str, float] = field(default_factory=dict)
    ai_rationale: str = ""
    ai_mode: str = "mock"  # "mock" | "live"

    @property
    def ai_confidence_pct(self) -> float:
        return self.ai_confidence * 100.0


@dataclass
class RoutingDecision:
    """Routing band + override resolution."""

    routing_outcome: str = ""  # human-readable, e.g. "Route to AE"
    band: str = ""  # AE | SDR | Nurture | Nurture (Low Priority)
    needs_human_review: bool = False
    proposal_required: bool = False
    overrides_applied: List[str] = field(default_factory=list)
    nurture_segment: str = ""


@dataclass
class RepBrief:
    account_summary: str = ""
    key_signals: List[str] = field(default_factory=list)
    likely_objections: List[Dict[str, str]] = field(default_factory=list)
    next_best_action: str = ""
    recommended_talk_track: str = ""
    confidence_notes: str = ""
    guardrail_fallback_used: bool = False


@dataclass
class EmailDraft:
    subject: str = ""
    body: str = ""
    call_to_action: str = ""
    guardrail_fallback_used: bool = False


@dataclass
class ProposalDraft:
    sections: List[Dict[str, Any]] = field(default_factory=list)
    needs_pricing_followup: bool = False
    needs_human_review: bool = True  # proposals are ALWAYS human-reviewed
    guardrail_fallback_used: bool = False


@dataclass
class MarketingEnrollment:
    platform: str = ""
    campaign_id: str = ""
    segment: str = ""
    enrolled_at: str = ""
    status: str = ""


@dataclass
class WorkflowResult:
    """Everything produced by a single ``run_workflow(lead_id)`` invocation."""

    run_id: str = ""
    lead: Optional[Lead] = None
    account: Optional[Account] = None
    data_quality: Optional[DataQualityResult] = None
    enrichment: Optional[EnrichmentResult] = None
    score: Optional[ScoreResult] = None
    routing: Optional[RoutingDecision] = None
    marketing_enrollment: Optional[MarketingEnrollment] = None
    rep_brief: Optional[RepBrief] = None
    email: Optional[EmailDraft] = None
    proposal: Optional[ProposalDraft] = None

    automation_mode: str = "mock"  # "mock" | "live"
    step_timings: Dict[str, float] = field(default_factory=dict)
    total_cycle_time_seconds: float = 0.0
    manual_baseline_seconds: float = 0.0
    time_saved_seconds: float = 0.0
    guardrail_fallback_used: bool = False
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

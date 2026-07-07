"""Scoring: a deterministic rule engine over structured CRM fields, blended
with an AI-confidence signal (mock keyword-scan over the Description, or a live
Claude rubric call).  ``combined_score = 0.6*rule + 0.4*(ai_confidence*100)``.

"Rules read the CRM, AI reads the notes" -- the two signals are deliberately
distinct so their disagreement is meaningful.

See plan section "Scoring & Routing".
"""
from __future__ import annotations

from typing import Dict, Optional

from .. import config
from ..models import Account, Lead, ScoreResult

W = config.SCORING_WEIGHTS

# Mock AI-confidence keyword scan. Presence-counted (each keyword contributes
# once), starting from a neutral base and clamped -- deterministic by design.
AI_BASE_CONFIDENCE = 0.45
AI_KEYWORD_WEIGHT = 0.08
AI_CONFIDENCE_MIN = 0.05
AI_CONFIDENCE_MAX = 0.98

POSITIVE_KEYWORDS = [
    "urgent", "board approved", "ready to buy", "decision maker", "immediate",
    "expansion", "renewal", "deadline", "funding secured", "pilot", "scaling",
    "procurement", "multi-year", "engaged", "allocated",
]
NEGATIVE_KEYWORDS = [
    "just researching", "no budget", "not sure", "exploring", "maybe next year",
    "student project", "unsubscribe", "not a priority", "curious", "browsing",
    "no timeline", "comparing competitors",
]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


# --- Rule engine -------------------------------------------------------------
def _employee_points(n: int) -> float:
    if n >= 5000:
        return W["employees_5000_plus"]
    if n >= 1000:
        return W["employees_1000_4999"]
    if n >= 250:
        return W["employees_250_999"]
    if n >= 50:
        return W["employees_50_249"]
    return W["employees_under_50"]


def _revenue_points(rev: float) -> float:
    if rev >= 100_000_000:
        return W["revenue_100m_plus"]
    if rev >= 25_000_000:
        return W["revenue_25m_100m"]
    if rev >= 5_000_000:
        return W["revenue_5m_25m"]
    return W["revenue_under_5m"]


def _leadsource_points(source: str) -> float:
    s = (source or "").lower()
    if s in config.LEADSOURCE_HIGH:
        return W["leadsource_high"]
    if s in config.LEADSOURCE_MEDIUM:
        return W["leadsource_medium"]
    return W["leadsource_low"]


def _timeline_points(timeline: str) -> float:
    t = (timeline or "").lower()
    if "quarter" in t:
        return W["timeline_this_quarter"]
    if "year" in t and "no" not in t:
        return W["timeline_this_year"]
    return W["timeline_none"]


def _industry_is_icp(industry: str) -> bool:
    return (industry or "").strip().lower() in config.ICP_INDUSTRIES


def compute_rule_score(lead: Lead) -> ScoreResult:
    """Deterministic firmographic + qualification rule score (0-100)."""
    breakdown: Dict[str, float] = {}
    breakdown["employees"] = _employee_points(lead.NumberOfEmployees)
    breakdown["revenue"] = _revenue_points(lead.AnnualRevenue)
    breakdown["icp_industry"] = (
        W["icp_industry_match"] if _industry_is_icp(lead.Industry) else 0.0
    )
    breakdown["lead_source"] = _leadsource_points(lead.LeadSource)
    breakdown["timeline"] = _timeline_points(lead.Timeline__c)
    breakdown["budget_confirmed"] = (
        W["budget_confirmed"] if lead.Budget_Confirmed__c else 0.0
    )
    breakdown["decision_maker"] = (
        W["decision_maker_identified"] if lead.DecisionMakerIdentified__c else 0.0
    )
    rule_score = _clamp(sum(breakdown.values()))
    return ScoreResult(rule_score=rule_score, rule_breakdown=breakdown)


# --- AI confidence (mock) ----------------------------------------------------
def compute_mock_ai_confidence(lead: Lead) -> ScoreResult:
    """Keyword-scan heuristic over the Description -> (confidence, rationale)."""
    text = (lead.Description or "").lower()
    pos = [k for k in POSITIVE_KEYWORDS if k in text]
    neg = [k for k in NEGATIVE_KEYWORDS if k in text]
    raw = AI_BASE_CONFIDENCE + AI_KEYWORD_WEIGHT * (len(pos) - len(neg))
    confidence = max(AI_CONFIDENCE_MIN, min(AI_CONFIDENCE_MAX, raw))

    parts = []
    if pos:
        parts.append(f"positive signals: {', '.join(pos)}")
    if neg:
        parts.append(f"caution signals: {', '.join(neg)}")
    if not parts:
        parts.append("no strong qualifying or disqualifying language detected")
    rationale = "Mock AI read of Description — " + "; ".join(parts) + "."
    return ScoreResult(ai_confidence=confidence, ai_rationale=rationale, ai_mode="mock")


# --- Blend -------------------------------------------------------------------
def score_lead(
    lead: Lead,
    account: Optional[Account] = None,
    ai_confidence: Optional[float] = None,
    ai_rationale: str = "",
    ai_mode: str = "mock",
) -> ScoreResult:
    """Produce the full ``ScoreResult`` (rule + AI + blended combined_score).

    When ``ai_confidence`` is supplied (e.g. from a live Claude call) it is used
    directly; otherwise the deterministic mock heuristic runs.
    """
    result = compute_rule_score(lead)

    if ai_confidence is None:
        ai = compute_mock_ai_confidence(lead)
        result.ai_confidence = ai.ai_confidence
        result.ai_rationale = ai.ai_rationale
        result.ai_mode = "mock"
    else:
        result.ai_confidence = max(0.0, min(1.0, float(ai_confidence)))
        result.ai_rationale = ai_rationale or "Live AI confidence."
        result.ai_mode = ai_mode

    result.combined_score = _clamp(
        config.RULE_BLEND * result.rule_score
        + config.AI_BLEND * (result.ai_confidence * 100.0)
    )
    return result

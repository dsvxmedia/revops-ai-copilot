"""Generation for the 3 LLM tasks (rep brief, follow-up email, proposal),
mock-first with a live-Claude path.

Flow per artifact:
  live mode -> call Claude -> guardrail-validate -> use if clean, else template
  mock mode -> deterministic template (which is ALSO the guardrail fallback)

The template generators are grounded in the lead/account record by construction,
so they always pass the guardrails and keep the demo deterministic.

See plan sections "Generation (3 LLM tasks...)" and "Guardrails".
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import config
from ..llm import claude_client, prompts
from ..models import (
    Account,
    EmailDraft,
    EnrichmentResult,
    Lead,
    ProposalDraft,
    RepBrief,
    RoutingDecision,
    ScoreResult,
)
from . import content_library_service, guardrails_service


# --- context building --------------------------------------------------------
def _context_payload(
    lead: Lead,
    account: Optional[Account],
    score: Optional[ScoreResult],
    routing: Optional[RoutingDecision],
    enrichment: Optional[EnrichmentResult],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "Company": lead.Company,
        "Contact": lead.full_name,
        "Title": lead.Title,
        "Industry": lead.Industry,
        "LeadSource": lead.LeadSource,
        "AnnualRevenue": lead.AnnualRevenue,
        "NumberOfEmployees": lead.NumberOfEmployees,
        "Timeline": lead.Timeline__c,
        "RequestType": lead.RequestType,
        "Description": lead.Description,
        "BudgetConfirmed": lead.Budget_Confirmed__c,
        "DecisionMakerIdentified": lead.DecisionMakerIdentified__c,
        "ExistingCustomer": lead.ExistingCustomer__c,
    }
    if account:
        payload["AccountType"] = account.Type
        payload["BillingState"] = account.BillingState
        payload["TechStack"] = ", ".join(account.TechStack or [])
    if score:
        payload["RuleScore"] = round(score.rule_score)
        payload["AIConfidencePct"] = round(score.ai_confidence_pct)
        payload["CombinedScore"] = round(score.combined_score)
    if routing:
        payload["RoutingOutcome"] = routing.routing_outcome
    if lead.opportunity:
        payload["OpportunityName"] = lead.opportunity.Name
        payload["OpportunityStage"] = lead.opportunity.StageName
        payload["OpportunityNextStep"] = lead.opportunity.NextStep
    return payload


def _context_text(payload: Dict[str, Any]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in payload.items())


# --- Rep brief ---------------------------------------------------------------
def _template_rep_brief(
    lead: Lead,
    account: Optional[Account],
    score: Optional[ScoreResult],
    routing: Optional[RoutingDecision],
    enrichment: Optional[EnrichmentResult],
) -> RepBrief:
    acct_type = account.Type if account else lead.Industry
    tech = ", ".join(account.TechStack) if account and account.TechStack else "no LMS on record"
    summary = (
        f"{lead.Company} is a {acct_type} organization in {lead.Industry} "
        f"with {lead.NumberOfEmployees} employees. Current stack: {tech}. "
        f"Inbound via {lead.LeadSource}."
    )

    signals: List[str] = []
    if lead.Budget_Confirmed__c:
        signals.append("Budget confirmed")
    if lead.DecisionMakerIdentified__c:
        signals.append(f"Decision maker identified ({lead.Title})")
    if lead.Timeline__c:
        signals.append(f"Timeline: {lead.Timeline__c}")
    if lead.ExistingCustomer__c:
        signals.append("Existing customer — expansion/renewal motion")
    if enrichment and enrichment.web_signal_used:
        signals.append("Live web signal captured during enrichment")
    if not signals:
        signals.append("Limited qualifying signals — treat as early-stage")

    objections = [
        {
            "objection": "We already have a content/LMS provider.",
            "suggested_response": (
                "Position integration with the existing stack "
                f"({tech}) and outcomes reporting rather than rip-and-replace."
            ),
        },
        {
            "objection": "Budget / procurement timing is unclear.",
            "suggested_response": (
                "Align to their stated timeline "
                f"({lead.Timeline__c or 'unspecified'}) and offer a scoped pilot."
            ),
        },
    ]

    nba = {
        "AE": "Schedule a consultative discovery call with the account owner this week.",
        "SDR": "Run a discovery call to qualify budget and timeline.",
    }.get(routing.band if routing else "", "Enroll in the appropriate nurture track and monitor engagement.")

    talk_track = (
        f"Lead with {lead.Industry} outcomes and integration with {tech}; "
        f"reference the {lead.LeadSource} touchpoint; keep it consultative, no pricing."
    )
    notes = (
        f"Rule score {round(score.rule_score) if score else 'n/a'}, "
        f"AI confidence {round(score.ai_confidence_pct) if score else 'n/a'}. "
        "Generated deterministically from the CRM record."
    )
    return RepBrief(
        account_summary=summary,
        key_signals=signals,
        likely_objections=objections,
        next_best_action=nba,
        recommended_talk_track=talk_track,
        confidence_notes=notes,
    )


def generate_rep_brief(
    lead: Lead,
    account: Optional[Account] = None,
    score: Optional[ScoreResult] = None,
    routing: Optional[RoutingDecision] = None,
    enrichment: Optional[EnrichmentResult] = None,
) -> RepBrief:
    payload = _context_payload(lead, account, score, routing, enrichment)
    ctx = _context_text(payload)

    if claude_client.is_available():
        data = claude_client.generate_json(
            prompts.REP_BRIEF_SYSTEM,
            prompts.build_context_block(payload),
            "rep_brief",
        )
        if data is not None:
            ok, _ = guardrails_service.validate("rep_brief", data, ctx)
            if ok:
                return RepBrief(
                    account_summary=data.get("account_summary", ""),
                    key_signals=list(data.get("key_signals", [])),
                    likely_objections=list(data.get("likely_objections", [])),
                    next_best_action=data.get("next_best_action", ""),
                    recommended_talk_track=data.get("recommended_talk_track", ""),
                    confidence_notes=data.get("confidence_notes", ""),
                    guardrail_fallback_used=False,
                )
        brief = _template_rep_brief(lead, account, score, routing, enrichment)
        brief.guardrail_fallback_used = True
        return brief

    return _template_rep_brief(lead, account, score, routing, enrichment)


# --- Follow-up email ---------------------------------------------------------
def _template_email(lead: Lead, account: Optional[Account], routing: Optional[RoutingDecision]) -> EmailDraft:
    band = routing.band if routing else ""
    tone_line = {
        "AE": "I'd love to set up a short consultative conversation about your goals",
        "SDR": "I'd like to learn more about your priorities and see if we're a fit",
    }.get(band, "I wanted to share a few resources that may be useful as you explore options")

    subject = f"{lead.Company} + Cengage — {lead.Industry} learning outcomes"
    body = (
        f"Hi {lead.FirstName},\n\n"
        f"Thanks for your interest via {lead.LeadSource}. Based on what you shared, "
        f"{tone_line}. We work with {lead.Industry} organizations to improve learning "
        f"outcomes and streamline course content, with integration into your existing tools.\n\n"
        f"If helpful, I can tailor this to {lead.Company}'s specific goals.\n\n"
        "Best regards,\nThe Cengage Team"
    )
    cta = {
        "AE": "Are you open to a 30-minute call this week?",
        "SDR": "Would a brief discovery call make sense?",
    }.get(band, "Would you like me to send a short overview tailored to your team?")
    return EmailDraft(subject=subject, body=body, call_to_action=cta)


def generate_email(
    lead: Lead, account: Optional[Account] = None, routing: Optional[RoutingDecision] = None
) -> EmailDraft:
    payload = _context_payload(lead, account, None, routing, None)
    ctx = _context_text(payload)

    if claude_client.is_available():
        data = claude_client.generate_json(
            prompts.EMAIL_SYSTEM, prompts.build_context_block(payload), "email"
        )
        if data is not None:
            ok, _ = guardrails_service.validate("email", data, ctx)
            if ok:
                return EmailDraft(
                    subject=data.get("subject", ""),
                    body=data.get("body", ""),
                    call_to_action=data.get("call_to_action", ""),
                    guardrail_fallback_used=False,
                )
        email = _template_email(lead, account, routing)
        email.guardrail_fallback_used = True
        return email

    return _template_email(lead, account, routing)


# --- Proposal / RFP draft ----------------------------------------------------
def _template_proposal(lead: Lead, account: Optional[Account]) -> ProposalDraft:
    acct_type = account.Type if account else "Higher Education"
    blocks = content_library_service.blocks_for_segment(acct_type)
    sections: List[Dict[str, Any]] = []
    for block in blocks:
        sections.append(
            {
                "title": block["title"],
                "content": block["body"],
                "content_block_ids": [block["id"]],
            }
        )
    if lead.RequestType == "RFP Request":
        rfp = content_library_service.get_block("CB-RFP-001")
        if rfp:
            sections.append(
                {
                    "title": rfp["title"],
                    "content": rfp["body"],
                    "content_block_ids": [rfp["id"]],
                }
            )

    # Pricing: always defer final commercial terms to the AE. Cite the approved
    # pricing block but keep the drafted line free of any specific dollar figure.
    pricing = content_library_service.pricing_block()
    pricing_ids = [pricing["id"]] if pricing else []
    sections.append(
        {
            "title": "Pricing & Commercial Terms",
            "content": "Pricing to be confirmed by the Account Executive based on enrollment and term length.",
            "content_block_ids": pricing_ids,
        }
    )
    return ProposalDraft(
        sections=sections,
        needs_pricing_followup=True,
        needs_human_review=True,
    )


def generate_proposal(lead: Lead, account: Optional[Account] = None) -> ProposalDraft:
    payload = _context_payload(lead, account, None, None, None)

    if claude_client.is_available():
        approved = content_library_service.blocks_for_segment(
            account.Type if account else "Higher Education"
        )
        approved_text = "\n".join(
            f"[{b['id']}] {b['title']}: {b['body']}" for b in approved
        )
        user_content = (
            prompts.build_context_block(payload)
            + "\n\nAPPROVED CONTENT BLOCKS (cite by id):\n"
            + approved_text
        )
        data = claude_client.generate_json(prompts.PROPOSAL_SYSTEM, user_content, "proposal")
        if data is not None:
            ok, _ = guardrails_service.validate("proposal", data)
            if ok:
                draft = ProposalDraft(
                    sections=list(data.get("sections", [])),
                    needs_pricing_followup=bool(data.get("needs_pricing_followup", True)),
                    guardrail_fallback_used=False,
                )
                draft.needs_human_review = True  # ALWAYS forced -- never trust LLM
                return draft
        draft = _template_proposal(lead, account)
        draft.guardrail_fallback_used = True
        draft.needs_human_review = True
        return draft

    return _template_proposal(lead, account)

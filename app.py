"""Streamlit entrypoint: the "Run the Copilot" screen.

Renders the pipeline sequentially so it plays like watching a real system run:
Lead Intake -> Data Quality -> Enrichment -> Scoring & Routing ->
[Marketing Enrollment] -> Rep Brief -> Follow-up Email -> [Proposal] -> Telemetry.

See plan sections "Streamlit App", "Marketing Automation Loop-Closing",
"Data Quality / Intake Hygiene".
"""
from __future__ import annotations

import time

import streamlit as st

from revops_copilot import config, ui_theme
from revops_copilot.orchestration import workflow

st.set_page_config(page_title="RevOps AI Copilot", layout="wide")
ui_theme.inject()


# --- Helpers -----------------------------------------------------------------
def routing_badge(routing) -> str:
    outcome = routing.routing_outcome
    if routing.needs_human_review:
        kind = "review"
    elif outcome.startswith("Route to AE"):
        kind = "ae"
    elif outcome.startswith("Route to SDR"):
        kind = "sdr"
    else:
        kind = "nurture"
    return ui_theme.badge(outcome, kind)


def mode_badge() -> str:
    if config.is_live_mode():
        return ui_theme.badge(config.mode_badge_label(), "ae")
    return ui_theme.badge("Mock / Template Mode", "neutral")


# --- Header ------------------------------------------------------------------
left, right = st.columns([0.7, 0.3])
with left:
    st.title("RevOps AI Copilot")
    st.caption(
        "Salesforce-centered lead intake, data quality, enrichment, scoring and routing, "
        "rep brief, email and proposal generation, and telemetry. "
        "Cengage AI Automation Engineer demo."
    )
with right:
    st.markdown(mode_badge(), unsafe_allow_html=True)
    if not config.is_live_mode():
        st.caption("Set `ANTHROPIC_API_KEY` to switch on live Claude generation.")


# --- Sidebar -----------------------------------------------------------------
st.sidebar.header("Run the Copilot")
lead_pairs = workflow.list_sample_leads()
label_to_id = {label: lead_id for lead_id, label in lead_pairs}
selected_label = st.sidebar.selectbox("Sample lead", list(label_to_id.keys()))
animate = st.sidebar.checkbox("Animate steps", value=True)
run_clicked = st.sidebar.button("Run Copilot", type="primary", use_container_width=True)
st.sidebar.divider()
st.sidebar.caption(
    "8 engineered scenarios: hot enterprise, cold SMB, RFP, ambiguous (human review), "
    "K-12 boundary, out-of-territory, corporate-training, existing-customer upsell."
)


def _pause(seconds: float):
    if animate:
        time.sleep(seconds)


# --- Run ---------------------------------------------------------------------
if run_clicked:
    lead_id = label_to_id[selected_label]
    try:
        result = workflow.run_workflow(lead_id)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Workflow failed: {exc}")
        st.stop()

    lead = result.lead

    # Step 1: Intake
    with st.status("1. Lead Intake", expanded=True) as s:
        c1, c2, c3 = st.columns(3)
        c1.metric("Company", lead.Company)
        c2.metric("Industry", lead.Industry or "-")
        c3.metric("Request Type", lead.RequestType)
        st.write(
            f"**{lead.full_name}** · {lead.Title or '-'} · {lead.Email or '-'} · "
            f"Source: {lead.LeadSource or '-'} · Territory: {lead.Territory__c or '-'}"
        )
        if lead.Description:
            st.caption(lead.Description)
        _pause(0.4)
        s.update(label="1. Lead Intake: loaded", state="complete")

    # Step 2: Data Quality
    dq = result.data_quality
    with st.status("2. Data Quality Check", expanded=True) as s:
        if dq.flags:
            for flag in dq.flags:
                st.write(f"- {flag}")
        else:
            st.write("No data-quality issues detected.")
        if dq.duplicate_of:
            st.markdown(
                ui_theme.note(
                    f"Possible duplicate of existing account: <strong>{dq.duplicate_of}</strong>",
                    "nurture",
                ),
                unsafe_allow_html=True,
            )
        _pause(0.5)
        s.update(label=f"2. Data Quality Check: {len(dq.flags)} flag(s)", state="complete")

    # Step 3: Enrichment
    enr = result.enrichment
    acct = result.account
    with st.status("3. Enrichment", expanded=True) as s:
        c1, c2, c3 = st.columns(3)
        c1.metric("Account Type", acct.Type if acct else "-")
        c2.metric("Employees", f"{acct.NumberOfEmployees:,}" if acct else "-")
        c3.metric("Billing State", acct.BillingState if acct else "-")
        st.write("**Tech stack (LMS/ed-tech):** " + (", ".join(acct.TechStack) if acct and acct.TechStack else "none detected"))
        tag = "live web signal" if enr and enr.web_signal_used else "simulated"
        st.caption(f"Enrichment source: {tag}")
        for enrichment_note in (enr.notes if enr else []):
            st.caption(f"- {enrichment_note}")
        _pause(0.5)
        s.update(label="3. Enrichment: complete", state="complete")

    # Step 4: Scoring & Routing
    score = result.score
    routing = result.routing
    with st.status("4. Scoring & Routing", expanded=True) as s:
        c1, c2, c3 = st.columns(3)
        c1.metric("Rule Score", f"{round(score.rule_score)}")
        c2.metric("AI Confidence", f"{round(score.ai_confidence_pct)}%")
        c3.metric("Combined Score", f"{round(score.combined_score)}")
        st.markdown("**Rule breakdown**")
        st.json({k: v for k, v in score.rule_breakdown.items()}, expanded=False)
        st.caption(score.ai_rationale)
        st.markdown("**Routing decision:** " + routing_badge(routing), unsafe_allow_html=True)
        for ov in routing.overrides_applied:
            st.markdown(ui_theme.note(f"Override: {ov}", "sdr"), unsafe_allow_html=True)
        if routing.needs_human_review:
            st.markdown(
                ui_theme.note(
                    "<strong>Needs human review</strong>: rule score and AI confidence "
                    "disagree beyond threshold.",
                    "review",
                ),
                unsafe_allow_html=True,
            )
        _pause(0.5)
        s.update(label=f"4. Scoring & Routing: {routing.routing_outcome}", state="complete")

    # Step 5: Marketing enrollment (conditional)
    if result.marketing_enrollment:
        me = result.marketing_enrollment
        with st.status("5. Marketing Campaign Enrollment", expanded=True) as s:
            st.markdown(
                ui_theme.note(
                    f"Enrolled in <strong>{me.segment}</strong> on <strong>{me.platform}</strong> "
                    f"(campaign <code>{me.campaign_id}</code>, {me.enrolled_at}).",
                    "ae",
                ),
                unsafe_allow_html=True,
            )
            _pause(0.4)
            s.update(label="5. Marketing Campaign Enrollment: enrolled", state="complete")

    # Step 6: Rep Brief
    brief = result.rep_brief
    with st.status("6. Rep Brief", expanded=True) as s:
        if brief.guardrail_fallback_used:
            st.markdown(
                ui_theme.note("Generated via fallback template. Review recommended.", "nurture"),
                unsafe_allow_html=True,
            )
        st.write(f"**Account summary:** {brief.account_summary}")
        st.write("**Key signals:** " + ", ".join(brief.key_signals))
        with st.expander("Likely objections & responses"):
            for ob in brief.likely_objections:
                st.write(f"- **{ob.get('objection')}**: {ob.get('suggested_response')}")
        st.write(f"**Next best action:** {brief.next_best_action}")
        st.caption(f"Talk track: {brief.recommended_talk_track}")
        _pause(0.4)
        s.update(label="6. Rep Brief: drafted", state="complete")

    # Step 7: Follow-up Email
    email = result.email
    with st.status("7. Follow-up Email", expanded=True) as s:
        if email.guardrail_fallback_used:
            st.markdown(
                ui_theme.note("Generated via fallback template. Review recommended.", "nurture"),
                unsafe_allow_html=True,
            )
        st.write(f"**Subject:** {email.subject}")
        st.text(email.body)
        st.write(f"**CTA:** {email.call_to_action}")
        _pause(0.4)
        s.update(label="7. Follow-up Email: drafted", state="complete")

    # Step 8: Proposal (conditional)
    if result.proposal:
        prop = result.proposal
        with st.status("8. Proposal / RFP Draft", expanded=True) as s:
            st.markdown(
                ui_theme.note(
                    "<strong>Needs human review</strong>: proposals are always gated to a "
                    "human before send.",
                    "review",
                ),
                unsafe_allow_html=True,
            )
            if prop.needs_pricing_followup:
                st.markdown(
                    ui_theme.note("Pricing to be confirmed by the Account Executive.", "sdr"),
                    unsafe_allow_html=True,
                )
            if prop.guardrail_fallback_used:
                st.markdown(
                    ui_theme.note(
                        "Generated via fallback template. Review recommended.", "nurture"
                    ),
                    unsafe_allow_html=True,
                )
            for section in prop.sections:
                with st.expander(f"{section.get('title')}  ·  cites {', '.join(section.get('content_block_ids', []) or ['-'])}"):
                    st.write(section.get("content"))
            _pause(0.4)
            s.update(label="8. Proposal / RFP Draft: drafted (human review required)", state="complete")

    # Step 9: Telemetry
    with st.status("9. Telemetry Recorded", expanded=True) as s:
        c1, c2, c3 = st.columns(3)
        c1.metric("Automated cycle time", f"{result.total_cycle_time_seconds:.3f}s")
        c2.metric("Manual baseline (illustrative)", f"{result.manual_baseline_seconds/60:.1f} min")
        saved_pct = (
            result.time_saved_seconds / result.manual_baseline_seconds * 100
            if result.manual_baseline_seconds else 0
        )
        c3.metric("Time saved (illustrative)", f"{saved_pct:.0f}%")
        st.caption("Per-step timing (seconds):")
        st.json(result.step_timings, expanded=False)
        st.caption(
            "Manual-baseline and pipeline-velocity figures are illustrative assumptions, "
            "not measured production data. See the Metrics Dashboard for the velocity model."
        )
        s.update(label="9. Telemetry Recorded", state="complete")

    st.markdown(
        ui_theme.note(
            f"Run complete for <strong>{lead.Company}</strong>: "
            f"<strong>{routing.routing_outcome}</strong> (run <code>{result.run_id[:8]}</code>). "
            "Open the Metrics Dashboard to see aggregate impact.",
            "ae",
        ),
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        ui_theme.note(
            "Pick a sample lead and select <strong>Run Copilot</strong>. Then explore "
            "<strong>Before vs After</strong> and the <strong>Metrics Dashboard</strong> "
            "in the sidebar. First time here? See <strong>How to Use</strong> in the "
            "sidebar for a full walkthrough.",
            "sdr",
        ),
        unsafe_allow_html=True,
    )

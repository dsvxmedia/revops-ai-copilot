"""Before vs After: manual process vs automated copilot, per scenario.

See plan section "Streamlit App".
"""
from __future__ import annotations

import json

import streamlit as st

from revops_copilot import config, ui_theme
from revops_copilot.orchestration import workflow

st.set_page_config(page_title="Before vs After — RevOps Copilot", layout="wide")
ui_theme.inject()
st.title("Before vs After")
st.caption("Manual RevOps process vs. the automated copilot, for the selected scenario.")

with open(config.MANUAL_BASELINE_PATH, "r", encoding="utf-8") as fh:
    baseline = json.load(fh).get("per_task_seconds", {})

lead_pairs = workflow.list_sample_leads()
label_to_id = {label: lead_id for lead_id, label in lead_pairs}
selected = st.selectbox("Scenario", list(label_to_id.keys()))
result = workflow.run_workflow(label_to_id[selected])

manual_total_min = sum(baseline.get(step, 0) for step in result.step_timings) / 60.0
auto_total_s = result.total_cycle_time_seconds

left, right = st.columns(2)
with left:
    st.subheader("Manual process (today)")
    st.markdown(
        "- Rep manually researches the company across tabs and tools\n"
        "- Scoring is ad hoc and inconsistent between reps\n"
        "- Rep drafts brief + email from scratch\n"
        "- RFP responses assembled by hand from old docs\n"
        "- Follow-up often delayed hours to days"
    )
    st.metric("Estimated manual effort (illustrative)", f"{manual_total_min:.1f} min")
    st.caption("Per-step manual assumptions (seconds):")
    st.json({k: baseline.get(k, 0) for k in result.step_timings}, expanded=False)

with right:
    st.subheader("Automated copilot")
    st.markdown(
        f"- Deterministic data-quality + enrichment pass\n"
        f"- Consistent, tunable scoring → **{result.routing.routing_outcome}**\n"
        f"- Rep brief + email generated automatically\n"
        f"- {'RFP proposal drafted (human-review gated)' if result.proposal else 'No proposal needed'}\n"
        f"- Runs in **{config.mode_badge_label()}**"
    )
    st.metric("Automated cycle time", f"{auto_total_s:.3f} s")
    if manual_total_min > 0:
        st.metric(
            "Time compression (illustrative)",
            f"{(1 - auto_total_s / (manual_total_min * 60)) * 100:.1f}%",
        )

st.divider()
st.subheader("Why this matters (qualitative)")
q1, q2, q3 = st.columns(3)
with q1:
    st.markdown(
        ui_theme.note("<strong>Consistency</strong> — every lead scored by the same tunable rubric, not gut feel.", "sdr"),
        unsafe_allow_html=True,
    )
with q2:
    st.markdown(
        ui_theme.note("<strong>Always-on</strong> — first-touch in seconds, not hours; no nights/weekends gap.", "sdr"),
        unsafe_allow_html=True,
    )
with q3:
    st.markdown(
        ui_theme.note("<strong>Auditable</strong> — guardrails, human-review gate, and telemetry on every run.", "sdr"),
        unsafe_allow_html=True,
    )

st.caption(
    "All manual-baseline and time-compression figures are illustrative assumptions for "
    "demonstration, not measured production data."
)

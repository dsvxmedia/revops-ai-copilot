"""Metrics Dashboard: KPI cards, cycle-time chart, routing distribution,
pipeline-velocity lift, and the raw run log.

Built with plain st.bar_chart / st.dataframe -- no pandas.

See plan sections "Streamlit App" and "Telemetry".
"""
from __future__ import annotations

import streamlit as st

from revops_copilot.orchestration import workflow
from revops_copilot.services import telemetry_service

st.set_page_config(page_title="Metrics Dashboard — RevOps Copilot", page_icon="📊", layout="wide")
st.title("📊 Metrics Dashboard")
st.caption("Aggregate telemetry across all runs recorded in the SQLite store.")

col_a, col_b = st.columns([0.7, 0.3])
with col_b:
    if st.button("▶ Run all 8 sample leads", use_container_width=True):
        for lead_id, _ in workflow.list_sample_leads():
            workflow.run_workflow(lead_id)
        st.success("Ran all 8 scenarios.")

summary = telemetry_service.compute_summary_metrics()
runs = telemetry_service.fetch_runs()

if summary["total_runs"] == 0:
    st.info("No runs yet. Click **Run all 8 sample leads** above, or run leads on the main page.")
    st.stop()

# --- KPI cards ---------------------------------------------------------------
st.subheader("Key metrics")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total runs", summary["total_runs"])
k2.metric("Automation success rate", f"{summary['automation_success_rate'] * 100:.0f}%")
k3.metric("Avg time saved (illustrative)", f"{summary['avg_time_saved_pct']:.0f}%")
k4.metric("Needing human review", f"{summary['pct_needing_human_review']:.0f}%")

# --- Pipeline velocity -------------------------------------------------------
pv = telemetry_service.compute_pipeline_velocity_impact()
st.subheader("Pipeline-velocity impact (illustrative model)")
p1, p2, p3 = st.columns(3)
p1.metric("Pipeline-velocity lift", f"+{pv['pipeline_velocity_lift_pct']:.1f}%")
p2.metric("Manual cycle (days)", f"{pv['manual_cycle_days']:.1f}")
p3.metric("Automated cycle (days)", f"{pv['automated_cycle_days']:.2f}")
st.caption(
    "Model: pipeline_velocity = (opportunities × win_rate × avg_deal_size) / cycle_days. "
    f"Assumes {pv['assumptions']['num_opportunities']} opps, "
    f"{pv['assumptions']['win_rate'] * 100:.0f}% win rate, "
    f"${pv['assumptions']['avg_deal_size']:,.0f} avg deal — "
    "response-time compression only. Illustrative, not a backtest."
)

# --- Cycle-time comparison ---------------------------------------------------
st.subheader("Cycle time: manual baseline vs automated")
avg_manual_min = summary["avg_manual_baseline_seconds"] / 60.0
avg_auto_min = summary["avg_cycle_time_seconds"] / 60.0
st.bar_chart(
    {"Minutes": {"Manual baseline": avg_manual_min, "Automated": max(avg_auto_min, 0.0001)}}
)

# --- Routing distribution ----------------------------------------------------
st.subheader("Routing-outcome distribution")
dist = telemetry_service.routing_distribution()
if dist:
    st.bar_chart({"Runs": dist})

# --- Raw run log -------------------------------------------------------------
st.subheader("Run log")
table = [
    {
        "Company": r["lead_company"],
        "Routing": r["routing_outcome"],
        "Score": round(r["combined_score"]),
        "Human review": "Yes" if r["needs_human_review"] else "No",
        "Proposal": "Yes" if r["proposal_generated"] else "No",
        "Fallback": "Yes" if r["guardrail_fallback_used"] else "No",
        "Mode": r["automation_mode"],
        "Cycle (s)": round(r["total_cycle_time_seconds"], 4),
        "When": r["created_at"],
    }
    for r in runs
]
st.dataframe(table, use_container_width=True, hide_index=True)

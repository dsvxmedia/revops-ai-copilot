"""Metrics Dashboard: KPI cards, cycle-time chart, routing distribution,
pipeline-velocity lift, and the raw run log.

All of our own data is plain dicts/lists -- no pandas DataFrames anywhere in
this project's own logic. The one `import pandas` below is not that; it's a
workaround for a third-party library thread-race bug, see its comment.

See plan sections "Streamlit App" and "Telemetry".
"""
from __future__ import annotations

# Force pandas fully loaded eagerly, in this page's own main-thread execution,
# before anything touches Altair. Altair's internal Chart.to_dict() does its
# own lazy `import pandas` on every call (to type-check for pd.Timestamp
# values) even though this project never imports pandas itself. If that lazy
# import's very first execution ever in the process races against
# Streamlit's background file-watcher thread also touching pandas, Python's
# import system can hand back a partially-initialized module and raise
# `AttributeError: partially initialized module 'pandas' ... (most likely due
# to a circular import)` -- a real bug hit during manual QA (rapid-fire
# "Run all 8 sample leads"), not a fluke. Doing the import here, synchronously,
# on every page load closes that race window.
import pandas  # noqa: F401

import altair as alt
import streamlit as st

from revops_copilot import ui_theme
from revops_copilot.orchestration import workflow
from revops_copilot.services import telemetry_service

st.set_page_config(page_title="Metrics Dashboard — RevOps Copilot", layout="wide")
ui_theme.inject()
st.title("Metrics Dashboard")
st.caption("Aggregate telemetry across all runs recorded in the SQLite store.")

col_a, col_b = st.columns([0.7, 0.3])
with col_b:
    if st.button("Run all 8 sample leads", use_container_width=True):
        for lead_id, _ in workflow.list_sample_leads():
            workflow.run_workflow(lead_id)
        st.markdown(
            ui_theme.note("Ran all 8 scenarios.", "ae"), unsafe_allow_html=True
        )

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

# --- Chart theme --------------------------------------------------------------
def _themed_bar(data: list[dict], x: str, y: str, color_map: dict | None = None) -> alt.Chart:
    base = alt.Chart(alt.Data(values=data)).mark_bar(size=34, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
    encode_kwargs = dict(
        x=alt.X(f"{x}:N", sort=None, title=None, axis=alt.Axis(labelAngle=0, labelColor=ui_theme.TEXT_MUTED, domainColor=ui_theme.BORDER, tickColor=ui_theme.BORDER)),
        y=alt.Y(f"{y}:Q", title=None, axis=alt.Axis(labelColor=ui_theme.TEXT_MUTED, gridColor=ui_theme.BORDER, domain=False, tickCount=4)),
        tooltip=[f"{x}:N", f"{y}:Q"],
    )
    if color_map:
        encode_kwargs["color"] = alt.Color(
            f"{x}:N",
            scale=alt.Scale(domain=list(color_map.keys()), range=list(color_map.values())),
            legend=None,
        )
    else:
        encode_kwargs["color"] = alt.value(ui_theme.ACCENT)
    return (
        base.encode(**encode_kwargs)
        .properties(height=260, background="transparent")
        .configure_view(strokeWidth=0)
    )


# --- Cycle-time comparison ---------------------------------------------------
st.subheader("Cycle time: manual baseline vs automated")
avg_manual_min = summary["avg_manual_baseline_seconds"] / 60.0
avg_auto_min = summary["avg_cycle_time_seconds"] / 60.0
cycle_data = [
    {"Series": "Automated", "Minutes": max(avg_auto_min, 0.0001)},
    {"Series": "Manual baseline", "Minutes": avg_manual_min},
]
st.altair_chart(
    _themed_bar(
        cycle_data,
        "Series",
        "Minutes",
        color_map={"Automated": ui_theme.ACCENT, "Manual baseline": ui_theme.BORDER},
    ),
    use_container_width=True,
)

# --- Routing distribution ----------------------------------------------------
st.subheader("Routing-outcome distribution")
dist = telemetry_service.routing_distribution()
if dist:
    dist_data = [{"Outcome": k, "Runs": v} for k, v in dist.items()]
    st.altair_chart(_themed_bar(dist_data, "Outcome", "Runs"), use_container_width=True)

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

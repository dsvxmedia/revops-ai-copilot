"""Telemetry: SQLite ``workflow_runs`` store + aggregate metrics, including the
illustrative pipeline-velocity impact model.

Distinct from the JSON-lines event log (``logs/events.log``): this is the
queryable aggregation store the Metrics Dashboard reads.

See plan section "Telemetry".
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import config
from ..models import WorkflowResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    lead_id TEXT,
    lead_company TEXT,
    scenario_label TEXT,
    created_at TEXT,
    step_durations_json TEXT,
    automation_mode TEXT,
    total_cycle_time_seconds REAL,
    manual_baseline_seconds REAL,
    time_saved_seconds REAL,
    combined_score REAL,
    routing_outcome TEXT,
    needs_human_review INTEGER,
    proposal_generated INTEGER,
    guardrail_fallback_used INTEGER
);
"""


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or str(config.DB_PATH)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def record_run(result: WorkflowResult, db_path: Optional[str] = None) -> None:
    """Persist a completed workflow run. Never raises upward."""
    try:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            lead = result.lead
            conn.execute(
                """
                INSERT OR REPLACE INTO workflow_runs (
                    run_id, lead_id, lead_company, scenario_label, created_at,
                    step_durations_json, automation_mode, total_cycle_time_seconds,
                    manual_baseline_seconds, time_saved_seconds, combined_score,
                    routing_outcome, needs_human_review, proposal_generated,
                    guardrail_fallback_used
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    result.run_id,
                    lead.Id if lead else "",
                    lead.Company if lead else "",
                    lead.scenario_label if lead else "",
                    result.created_at,
                    json.dumps(result.step_timings),
                    result.automation_mode,
                    result.total_cycle_time_seconds,
                    result.manual_baseline_seconds,
                    result.time_saved_seconds,
                    result.score.combined_score if result.score else 0.0,
                    result.routing.routing_outcome if result.routing else "",
                    1 if (result.routing and result.routing.needs_human_review) else 0,
                    1 if result.proposal else 0,
                    1 if result.guardrail_fallback_used else 0,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - telemetry must never break the workflow
        pass


def fetch_runs(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        init_db(db_path)
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM workflow_runs ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return []


def compute_summary_metrics(db_path: Optional[str] = None) -> Dict[str, Any]:
    runs = fetch_runs(db_path)
    total = len(runs)
    if total == 0:
        return {
            "total_runs": 0,
            "avg_cycle_time_seconds": 0.0,
            "avg_manual_baseline_seconds": 0.0,
            "avg_time_saved_pct": 0.0,
            "automation_success_rate": 1.0,
            "pct_needing_human_review": 0.0,
        }

    avg_cycle = sum(r["total_cycle_time_seconds"] or 0 for r in runs) / total
    avg_manual = sum(r["manual_baseline_seconds"] or 0 for r in runs) / total
    saved_pcts = []
    for r in runs:
        manual = r["manual_baseline_seconds"] or 0
        if manual > 0:
            saved_pcts.append((r["time_saved_seconds"] or 0) / manual * 100.0)
    avg_saved_pct = sum(saved_pcts) / len(saved_pcts) if saved_pcts else 0.0
    fallback_count = sum(1 for r in runs if r["guardrail_fallback_used"])
    review_count = sum(1 for r in runs if r["needs_human_review"])

    return {
        "total_runs": total,
        "avg_cycle_time_seconds": round(avg_cycle, 3),
        "avg_manual_baseline_seconds": round(avg_manual, 1),
        "avg_time_saved_pct": round(avg_saved_pct, 1),
        "automation_success_rate": round(1.0 - fallback_count / total, 3),
        "pct_needing_human_review": round(review_count / total * 100.0, 1),
    }


def routing_distribution(db_path: Optional[str] = None) -> Dict[str, int]:
    dist: Dict[str, int] = {}
    for r in fetch_runs(db_path):
        outcome = r["routing_outcome"] or "Unknown"
        dist[outcome] = dist.get(outcome, 0) + 1
    return dist


def _manual_baseline_config() -> Dict[str, Any]:
    try:
        with open(config.MANUAL_BASELINE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def compute_pipeline_velocity_impact(db_path: Optional[str] = None) -> Dict[str, Any]:
    """ILLUSTRATIVE pipeline-velocity lift from response-time compression.

    pipeline_velocity = (num_opps * win_rate * avg_deal_size) / cycle_length_days

    Computed once with the manual first-response latency and once with the
    automated latency, holding win_rate and deal size constant. NOT a backtest.
    """
    a = config.PIPELINE_VELOCITY_ASSUMPTIONS
    baseline = _manual_baseline_config()

    days_per_hour = a["days_added_per_response_hour"]
    manual_hours = baseline.get("assumed_first_response_hours_manual", 24)
    auto_hours = baseline.get("assumed_first_response_hours_automated", 0.05)

    manual_cycle_days = a["base_cycle_days"] + manual_hours * days_per_hour
    auto_cycle_days = a["base_cycle_days"] + auto_hours * days_per_hour

    numerator = a["num_opportunities"] * a["win_rate"] * a["avg_deal_size"]
    velocity_manual = numerator / manual_cycle_days
    velocity_auto = numerator / auto_cycle_days

    lift_pct = (velocity_auto - velocity_manual) / velocity_manual * 100.0
    delta_dollars = velocity_auto - velocity_manual

    return {
        "illustrative": True,
        "assumptions": {
            "num_opportunities": a["num_opportunities"],
            "win_rate": a["win_rate"],
            "avg_deal_size": a["avg_deal_size"],
            "base_cycle_days": a["base_cycle_days"],
            "manual_first_response_hours": manual_hours,
            "automated_first_response_hours": auto_hours,
        },
        "manual_cycle_days": round(manual_cycle_days, 2),
        "automated_cycle_days": round(auto_cycle_days, 2),
        "pipeline_velocity_manual": round(velocity_manual, 2),
        "pipeline_velocity_automated": round(velocity_auto, 2),
        "pipeline_velocity_lift_pct": round(lift_pct, 1),
        "pipeline_velocity_delta_per_day": round(delta_dollars, 2),
    }

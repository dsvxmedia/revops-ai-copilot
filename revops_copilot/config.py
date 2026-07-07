"""Environment / configuration, model default, and tunable scoring constants.

Nothing here requires an API key. Presence of ``ANTHROPIC_API_KEY`` toggles
mock vs. live generation; everything degrades gracefully when it's absent.

See plan sections "Config / Model" and "Scoring & Routing".
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Optional .env loading (python-dotenv is optional; never required) -------
# Deliberately load ONLY this project's own .env (next to this package), not
# python-dotenv's default upward directory search -- that default walks every
# ancestor directory looking for a file named ".env" and would silently pick
# up an unrelated one (e.g. a developer's global ~/.env with their own
# personal API keys), breaking this project's "deterministic mock mode by
# default, no key required" guarantee for anyone with such a file.
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv

    _PROJECT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_PROJECT_ENV_PATH)
except Exception:  # noqa: BLE001 - a missing dotenv must never break the app
    pass


# --- Paths -------------------------------------------------------------------
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PACKAGE_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
DB_PATH = PROJECT_ROOT / "revops_copilot.db"
EVENTS_LOG_PATH = LOGS_DIR / "events.log"

SAMPLE_LEADS_PATH = DATA_DIR / "sample_leads.json"
CONTENT_BLOCKS_PATH = DATA_DIR / "content_blocks.json"
MANUAL_BASELINE_PATH = DATA_DIR / "manual_baseline.json"


# --- Model / mode ------------------------------------------------------------
# Default model id per the approved plan. Kept configurable via env so a live
# run can override it without a code change. See LEARNING.md for the note on
# verifying this id against Anthropic's current model list.
DEFAULT_MODEL = "claude-sonnet-5"
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
OPIK_API_KEY = os.environ.get("OPIK_API_KEY", "").strip()

# Live Claude calls: short, demo-safe budget.
LLM_MAX_TOKENS = int(os.environ.get("REVOPS_LLM_MAX_TOKENS", "1500"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("REVOPS_LLM_TIMEOUT", "30"))


def is_live_mode() -> bool:
    """Live generation is enabled only when an Anthropic key is present."""
    return bool(ANTHROPIC_API_KEY)


def automation_mode() -> str:
    return "live" if is_live_mode() else "mock"


def mode_badge_label() -> str:
    if is_live_mode():
        return f"Live Claude Mode — model: {ANTHROPIC_MODEL}"
    return "Mock/Template Mode"


# --- Enrichment (Scrapling web fetch) ----------------------------------------
# OFF by default so the primary mock demo is deterministic and needs no network.
# Set REVOPS_WEB_ENRICHMENT=1 to enable the real (best-effort) Scrapling fetch;
# it still falls back to mock on any failure.
WEB_ENRICHMENT_ENABLED = os.environ.get("REVOPS_WEB_ENRICHMENT", "0") == "1"
WEB_FETCH_TIMEOUT_SECONDS = 5.0
WEB_FETCH_USER_AGENT = "RevOpsCopilotDemo/1.0 (+portfolio-demo; contact dsvxmedia@gmail.com)"

# Known LMS / ed-tech vendor names we look for on a company site as a signal.
KNOWN_EDTECH_VENDORS = [
    "Canvas",
    "Blackboard",
    "Moodle",
    "Brightspace",
    "D2L",
    "Cengage",
    "McGraw Hill",
    "Pearson",
    "Google Classroom",
    "Schoology",
]


# --- Scoring weights (named + tunable; a callout in the demo) ----------------
# These are deterministic contributions summed then clamped to 0-100 as
# ``rule_score``. "The business can tune this without touching model code."
SCORING_WEIGHTS = {
    # Firmographic: employee-count bands
    "employees_5000_plus": 20.0,
    "employees_1000_4999": 15.0,
    "employees_250_999": 10.0,
    "employees_50_249": 5.0,
    "employees_under_50": 0.0,
    # Firmographic: annual-revenue bands (USD)
    "revenue_100m_plus": 20.0,
    "revenue_25m_100m": 14.0,
    "revenue_5m_25m": 8.0,
    "revenue_under_5m": 2.0,
    # ICP industry match (Cengage-relevant verticals)
    "icp_industry_match": 15.0,
    # Lead source weighting
    "leadsource_high": 12.0,  # e.g. RFP / Partner Referral / Web Demo Request
    "leadsource_medium": 7.0,  # e.g. Webinar / Content Download
    "leadsource_low": 2.0,  # e.g. List Purchase / Cold
    # Timeline urgency
    "timeline_this_quarter": 12.0,
    "timeline_this_year": 6.0,
    "timeline_none": 0.0,
    # Explicit qualification bonuses
    "budget_confirmed": 8.0,
    "decision_maker_identified": 8.0,
}

# ICP industries considered an on-brand match for Cengage.
ICP_INDUSTRIES = {
    "higher education",
    "education",
    "k-12 education",
    "k-12",
    "primary/secondary education",
    "government/public sector",
    "workforce development",
    "corporate training",
    "professional training & coaching",
}

# High / medium / low lead-source buckets.
LEADSOURCE_HIGH = {"rfp request", "partner referral", "web demo request", "referral", "rfp"}
LEADSOURCE_MEDIUM = {"webinar", "content download", "event", "trade show", "web"}

# Blend weights: combined = RULE_BLEND*rule + AI_BLEND*(ai_confidence*100)
RULE_BLEND = 0.6
AI_BLEND = 0.4

# Routing band thresholds (on combined_score, 0-100).
BAND_AE_MIN = 75.0
BAND_SDR_MIN = 50.0
BAND_NURTURE_MIN = 25.0

# Rule vs. AI disagreement threshold -> forces Needs Human Review.
DISAGREEMENT_THRESHOLD = 30.0

# In-territory values for the out-of-territory override.
IN_TERRITORY = {"NAMER", "North America", "US", "USA", "United States", "AMER", "West", "East", "Central"}


# --- Pipeline-velocity model (illustrative) ----------------------------------
# Used by telemetry_service.compute_pipeline_velocity_impact(). Labelled
# illustrative in the UI -- NOT measured production data.
PIPELINE_VELOCITY_ASSUMPTIONS = {
    "num_opportunities": 40,
    "win_rate": 0.22,
    "avg_deal_size": 85000.0,
    # Sales-cycle length is modelled as a base plus response latency.
    # Faster first-touch (automation) compresses the effective cycle.
    "base_cycle_days": 60.0,
    # How many days one hour of response-time delay is assumed to add.
    "days_added_per_response_hour": 0.5,
}

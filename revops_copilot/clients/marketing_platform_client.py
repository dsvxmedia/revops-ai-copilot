"""Marketing-platform client stub (Marketo / HubSpot / SFMC-shaped).

``enroll_in_nurture_campaign()`` is genuinely called by the orchestration layer
for every Nurture-routed lead -- it closes the sales->marketing handoff loop
instead of leaving the client as dead code.

See plan section "Marketing Automation Loop-Closing".
"""
from __future__ import annotations

import time
import uuid
from typing import Dict

from ..models import Lead, MarketingEnrollment
from ..logging_config import log_event


# Segment mapping derived from Industry / Account Type.
def derive_segment(lead: Lead) -> str:
    industry = (lead.Industry or "").lower()
    if "k-12" in industry or "primary" in industry or "secondary" in industry:
        return "K-12 Nurture Track"
    if "corporate" in industry or "workforce" in industry or "training" in industry:
        return "Workforce Nurture Track"
    if "higher" in industry or "education" in industry:
        return "Higher-Ed Nurture Track"
    if "government" in industry or "public" in industry or "library" in industry:
        return "Public-Sector Nurture Track"
    return "General Nurture Track"


class MarketingPlatformClient:
    """Stub shaped like a Marketo/HubSpot/SFMC integration client."""

    def __init__(self, platform: str = "HubSpot"):
        self.platform = platform

    def enroll_in_nurture_campaign(self, lead: Lead, segment: str = "") -> MarketingEnrollment:
        """Return a mock campaign-enrollment confirmation.

        Mirrors what a real ``client.marketing.campaigns.enroll(...)`` call would
        hand back: platform, campaign id, and an enrolled-at timestamp.
        """
        segment = segment or derive_segment(lead)
        campaign_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
        enrolled_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log_event(
            "nurture_enrollment",
            lead_id=lead.Id,
            platform=self.platform,
            segment=segment,
            campaign_id=campaign_id,
        )
        return MarketingEnrollment(
            platform=self.platform,
            campaign_id=campaign_id,
            segment=segment,
            enrolled_at=enrolled_at,
            status="enrolled",
        )

    def as_dict(self) -> Dict[str, str]:
        return {"platform": self.platform}

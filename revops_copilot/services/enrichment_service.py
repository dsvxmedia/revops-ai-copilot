"""Enrichment orchestration: calls the enrichment client (web-first, mock
fallback) and returns a merged ``EnrichmentResult``.

Kept thin on purpose -- the fallback logic lives in the client so the service
just picks the client and records a structured event.

See plan section "Observability & Real Enrichment".
"""
from __future__ import annotations

from typing import Optional

from ..clients.enrichment_client import EnrichmentClient, get_enrichment_client
from ..logging_config import log_event
from ..models import EnrichmentResult, Lead


def enrich_lead(lead: Lead, client: Optional[EnrichmentClient] = None) -> EnrichmentResult:
    client = client or get_enrichment_client()
    try:
        result = client.enrich(lead)
    except Exception as exc:  # noqa: BLE001 - defensive: never break the workflow
        log_event("enrichment_error", lead_id=lead.Id, reason=str(exc)[:200])
        from ..clients.enrichment_client import MockEnrichmentClient

        result = MockEnrichmentClient().enrich(lead)
    log_event(
        "enrichment_complete",
        lead_id=lead.Id,
        web_signal_used=result.web_signal_used,
        tech_stack=result.account.TechStack if result.account else [],
    )
    return result

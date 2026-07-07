"""Enrichment clients: an abstract base, a deterministic mock, and a real
(best-effort) Scrapling-based web client that falls back to the mock on ANY
failure -- missing package, no website, offline, blocked, or robots-disallowed.

See plan section "Observability & Real Enrichment (added integrations)".
"""
from __future__ import annotations

import abc
import socket
from contextlib import contextmanager
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from .. import config
from ..models import Account, EnrichmentResult, Lead
from ..logging_config import log_event


class EnrichmentClient(abc.ABC):
    """Interface for a source that augments a Lead into an enriched Account."""

    @abc.abstractmethod
    def enrich(self, lead: Lead) -> EnrichmentResult:  # pragma: no cover - abstract
        raise NotImplementedError


class MockEnrichmentClient(EnrichmentClient):
    """Deterministic firmographic enrichment derived from the lead's seed data.

    This is the always-available baseline: no network, no external package.
    """

    def enrich(self, lead: Lead) -> EnrichmentResult:
        seed = dict(lead.account_seed or {})
        account = Account.from_dict(seed)

        # Fill from the Lead where the seed is silent.
        if not account.Name:
            account.Name = lead.Company
        if not account.AnnualRevenue:
            account.AnnualRevenue = lead.AnnualRevenue
        if not account.NumberOfEmployees:
            account.NumberOfEmployees = lead.NumberOfEmployees
        if not account.Type:
            account.Type = _infer_type(lead.Industry)
        account.ExistingCustomer = bool(
            account.ExistingCustomer or lead.ExistingCustomer__c
        )

        sources: Dict[str, str] = {
            "Name": "simulated",
            "Type": "simulated",
            "AnnualRevenue": "simulated",
            "NumberOfEmployees": "simulated",
            "BillingState": "simulated",
            "Website": "simulated",
            "TechStack": "simulated",
        }
        return EnrichmentResult(
            account=account,
            field_sources=sources,
            web_signal_used=False,
            notes=["Firmographics from mock enrichment provider (simulated)."],
        )


class WebEnrichmentClient(EnrichmentClient):
    """Real, best-effort enrichment via Scrapling on the Account ``Website``.

    Etiquette: single request, ~5s timeout, identifying User-Agent, and a
    robots.txt check before fetching. ANY failure -> silently fall back to the
    MockEnrichmentClient output only (the UI notes which fields were live).
    """

    def __init__(self) -> None:
        self._mock = MockEnrichmentClient()

    def enrich(self, lead: Lead) -> EnrichmentResult:
        base = self._mock.enrich(lead)
        if not config.WEB_ENRICHMENT_ENABLED:
            return base

        website = base.account.Website if base.account else ""
        if not website:
            base.notes.append("No website on record — web enrichment skipped.")
            return base

        try:
            title, meta, vendors = self._fetch_signals(website)
        except Exception as exc:  # noqa: BLE001 - graceful degrade is the whole point
            log_event(
                "web_enrichment_fallback",
                website=website,
                reason=str(exc)[:200],
            )
            base.notes.append("Web enrichment failed — using simulated data only.")
            return base

        if title:
            base.notes.append(f"Live page title: {title[:120]}")
            base.field_sources["Website"] = "live web signal"
        if meta:
            base.notes.append(f"Live meta description: {meta[:160]}")
        if vendors:
            merged = list(dict.fromkeys((base.account.TechStack or []) + vendors))
            base.account.TechStack = merged
            base.field_sources["TechStack"] = "live web signal"
            base.notes.append(f"Detected ed-tech vendor mentions: {', '.join(vendors)}")

        base.web_signal_used = bool(title or meta or vendors)
        return base

    # --- internals -----------------------------------------------------------
    def _robots_allows(self, website: str) -> bool:
        try:
            import urllib.robotparser

            parsed = urlparse(website)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            parser.read()
            return parser.can_fetch(config.WEB_FETCH_USER_AGENT, website)
        except Exception:  # noqa: BLE001 - if robots can't be read, be conservative
            return False

    @contextmanager
    def _socket_timeout(self):
        """Bound any blocking network read (incl. robots.txt) to the timeout."""
        previous = socket.getdefaulttimeout()
        socket.setdefaulttimeout(config.WEB_FETCH_TIMEOUT_SECONDS)
        try:
            yield
        finally:
            socket.setdefaulttimeout(previous)

    def _fetch_signals(self, website: str) -> Tuple[str, str, List[str]]:
      with self._socket_timeout():
        # Guarded import: absence of scrapling must never raise upward.
        try:
            from scrapling.fetchers import Fetcher  # type: ignore
        except Exception:  # noqa: BLE001
            try:
                from scrapling import Fetcher  # type: ignore
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("scrapling not importable") from exc

        if not self._robots_allows(website):
            raise RuntimeError("robots.txt disallows fetch")

        page = Fetcher.get(
            website,
            timeout=config.WEB_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": config.WEB_FETCH_USER_AGENT},
        )

        title = ""
        meta = ""
        try:
            node = page.css_first("title")
            if node is not None:
                title = (node.text or "").strip()
        except Exception:  # noqa: BLE001
            pass
        try:
            node = page.css_first('meta[name="description"]')
            if node is not None:
                meta = (node.attrib.get("content") or "").strip()
        except Exception:  # noqa: BLE001
            pass

        try:
            body_text = page.get_all_text() or ""
        except Exception:  # noqa: BLE001
            body_text = ""
        haystack = f"{title} {meta} {body_text}".lower()
        vendors = [v for v in config.KNOWN_EDTECH_VENDORS if v.lower() in haystack]

        return title, meta, vendors


def _infer_type(industry: str) -> str:
    text = (industry or "").lower()
    if "k-12" in text or "primary" in text or "secondary" in text:
        return "K-12"
    if "higher" in text or "education" in text:
        return "Higher Education"
    if "corporate" in text or "workforce" in text or "training" in text:
        return "Workforce/Corporate Training"
    if "government" in text or "public" in text or "library" in text:
        return "Library/Public Sector"
    return "Higher Education"


def get_enrichment_client() -> EnrichmentClient:
    """Prefer the real web client (which itself falls back to mock)."""
    if config.WEB_ENRICHMENT_ENABLED:
        return WebEnrichmentClient()
    return MockEnrichmentClient()

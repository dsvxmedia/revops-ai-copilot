"""Mock Salesforce CRM client, shaped like ``simple_salesforce``.

Loads the 8 sample leads from ``data/sample_leads.json`` and exposes a small
``.query`` / record-access surface plus a write-back method, so the workflow
reads/writes "Salesforce" the way it would against a real org -- swappable for
``simple_salesforce`` later.

See plan section "Data Model" / folder-structure notes.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .. import config
from ..models import Lead

# Existing Accounts already "in the CRM". Used by the data-quality service for
# fuzzy duplicate-company detection. Note "BrightPath Tutoring, Inc." here vs.
# the sample lead's "BrightPath Tutoring LLC" -- an intentional near-duplicate.
KNOWN_ACCOUNTS: List[str] = [
    "BrightPath Tutoring, Inc.",
    "Great Lakes State University System",
    "Northgate Technical College",
    "Pinnacle Adult Education Center",
    "Cascade Public Library Network",
]


class MockSalesforceClient:
    """A tiny in-memory stand-in for ``simple_salesforce.Salesforce``."""

    def __init__(self, leads_path: Optional[str] = None):
        self._leads_path = leads_path or str(config.SAMPLE_LEADS_PATH)
        self._raw_leads: List[Dict[str, Any]] = []
        self._writebacks: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self._leads_path, "r", encoding="utf-8") as fh:
                self._raw_leads = json.load(fh)
        except Exception:  # noqa: BLE001 - never crash the demo on data load
            self._raw_leads = []

    # --- simple_salesforce-shaped read surface -------------------------------
    def list_leads(self) -> List[Lead]:
        """Return all sample leads as ``Lead`` dataclasses (UI dropdown source)."""
        return [Lead.from_dict(r) for r in self._raw_leads]

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        for record in self._raw_leads:
            if record.get("Id") == lead_id:
                return Lead.from_dict(record)
        return None

    def get_lead_raw(self, lead_id: str) -> Optional[Dict[str, Any]]:
        for record in self._raw_leads:
            if record.get("Id") == lead_id:
                return record
        return None

    def query(self, soql: str) -> Dict[str, Any]:
        """Very small SOQL-shaped shim: returns all leads regardless of filter.

        Real ``simple_salesforce`` returns ``{"totalSize", "records": [...]}``;
        we mirror that shape so calling code looks realistic.
        """
        records = list(self._raw_leads)
        return {"totalSize": len(records), "done": True, "records": records}

    def known_account_names(self) -> List[str]:
        names = list(KNOWN_ACCOUNTS)
        for record in self._raw_leads:
            acct = record.get("Account") or {}
            name = acct.get("Name")
            if name and name not in names:
                names.append(name)
        return names

    # --- write-back surface --------------------------------------------------
    def update_lead(self, lead_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate ``sf.Lead.update(id, fields)`` -> writes AI_* fields back.

        In a real org these would be ``AI_Score__c``, ``AI_Routing__c``, etc.
        Here we just record them and return a Salesforce-style success payload.
        """
        self._writebacks.setdefault(lead_id, {}).update(fields)
        return {"id": lead_id, "success": True, "errors": []}

    def get_writebacks(self, lead_id: str) -> Dict[str, Any]:
        return dict(self._writebacks.get(lead_id, {}))

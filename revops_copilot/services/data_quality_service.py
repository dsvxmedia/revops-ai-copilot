"""Intake hygiene: missing-field flags, light normalization, and fuzzy
duplicate-company detection using stdlib ``difflib.SequenceMatcher`` only.

See plan section "Data Quality / Intake Hygiene".
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List, Optional

from ..models import DataQualityResult, Lead

# Critical fields whose absence we flag before scoring.
CRITICAL_FIELDS = ["Email", "Company", "AnnualRevenue", "NumberOfEmployees"]

# Ratio at/above which two normalized company names are treated as duplicates.
DUPLICATE_RATIO_THRESHOLD = 0.85

# Legal / entity suffix tokens stripped during company-name normalization.
_ENTITY_SUFFIXES = {
    "inc", "incorporated", "llc", "llp", "corp", "corporation",
    "co", "company", "ltd", "limited", "plc", "the",
}


def _normalize_company(name: str) -> str:
    text = (name or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if t and t not in _ENTITY_SUFFIXES]
    return " ".join(tokens)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_duplicate_company(
    company: str, known_names: List[str]
) -> Optional[str]:
    """Return the known account name that is a near-duplicate of ``company``.

    Ignores exact raw-string matches (that record simply *is* that account);
    we only flag near-duplicates that differ in raw form -- the real data
    hygiene problem (two records for one company).
    """
    target = _normalize_company(company)
    if not target:
        return None
    best_name = None
    best_ratio = 0.0
    for known in known_names:
        if known == company:  # same raw record, not a hygiene problem
            continue
        ratio = _similarity(target, _normalize_company(known))
        if ratio > best_ratio:
            best_ratio = ratio
            best_name = known
    if best_ratio >= DUPLICATE_RATIO_THRESHOLD:
        return best_name
    return None


def check_lead(lead: Lead, known_account_names: Optional[List[str]] = None) -> DataQualityResult:
    """Run the deterministic intake-hygiene pass over a single Lead."""
    flags: List[str] = []
    normalized = {}

    # Missing / blank critical fields.
    for f in CRITICAL_FIELDS:
        value = getattr(lead, f, None)
        if value in (None, "", 0, 0.0):
            flags.append(f"Missing critical field: {f}")

    # Light normalization (email casing/whitespace, phone digits).
    if lead.Email:
        cleaned_email = lead.Email.strip().lower()
        if cleaned_email != lead.Email:
            normalized["Email"] = cleaned_email
            flags.append("Email normalized (whitespace/casing)")
    if lead.Phone:
        digits = re.sub(r"\D", "", lead.Phone)
        if digits and not re.search(r"[()\-\s]", lead.Phone) and len(digits) >= 10:
            normalized["Phone"] = _format_phone(digits)
            flags.append("Phone normalized to standard format")

    # Fuzzy duplicate-company detection.
    duplicate_of = ""
    if known_account_names:
        match = find_duplicate_company(lead.Company, known_account_names)
        if match:
            duplicate_of = match
            flags.append(f"Possible duplicate company: '{lead.Company}' ~ '{match}'")

    passed = not any(f.startswith("Missing critical field") for f in flags)
    return DataQualityResult(
        flags=flags,
        normalized_fields=normalized,
        duplicate_of=duplicate_of,
        passed=passed,
    )


def _format_phone(digits: str) -> str:
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("1"):
        d = digits[1:]
        return f"+1 ({d[0:3]}) {d[3:6]}-{d[6:]}"
    return digits

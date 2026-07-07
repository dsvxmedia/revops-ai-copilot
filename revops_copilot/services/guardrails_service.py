"""Guardrails over all LLM-generated output.

Common checks: required keys/types, non-empty strings, max-length sanity bound,
PII-leak regex scan, profanity denylist. Proposal-specific: every cited
``content_block_id`` must exist (fabrication guard) and any ``$``-number must
trace to an approved block. Rep brief / email: a lightweight grounding heuristic
(numbers in the output should appear in the input record).

On ANY failure the caller falls back to the deterministic template generator and
sets ``guardrail_fallback_used=True``. No retries -- straight to fallback.

See plan section "Guardrails".
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set, Tuple

from ..logging_config import log_event
from . import content_library_service

MAX_FIELD_CHARS = 6000

# PII patterns we must never emit (US SSN, long card-like digit runs).
_PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),  # card-like
]

_PROFANITY = {"damn", "hell", "shit", "fuck", "bastard", "crap", "asshole"}

_NUMBER_RE = re.compile(r"\d[\d,]{1,}")
_MONEY_RE = re.compile(r"\$\s?[\d,]+(?:\.\d+)?")


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def _check_required(data: Dict[str, Any], required: Dict[str, type]) -> List[str]:
    failures = []
    for key, expected in required.items():
        if key not in data:
            failures.append(f"missing required key: {key}")
            continue
        if not isinstance(data[key], expected):
            failures.append(
                f"key {key} has wrong type: expected {expected.__name__}"
            )
    return failures


def _check_strings(data: Dict[str, Any], nonempty_keys: List[str]) -> List[str]:
    failures = []
    for key in nonempty_keys:
        val = data.get(key)
        if isinstance(val, str) and not val.strip():
            failures.append(f"empty string for key: {key}")
    for s in _iter_strings(data):
        if len(s) > MAX_FIELD_CHARS:
            failures.append("field exceeds max length sanity bound")
            break
    return failures


def _check_safety(data: Dict[str, Any]) -> List[str]:
    failures = []
    for s in _iter_strings(data):
        for pat in _PII_PATTERNS:
            if pat.search(s):
                failures.append("possible PII leak detected in output")
                break
        low = s.lower()
        if any(re.search(rf"\b{re.escape(word)}\b", low) for word in _PROFANITY):
            failures.append("profanity detected in output")
    return failures


def _numbers_in(text: str) -> Set[str]:
    return {m.replace(",", "") for m in _NUMBER_RE.findall(text or "")}


def _check_grounding(data: Dict[str, Any], context_text: str) -> List[str]:
    """Numbers appearing in the output should be traceable to the input."""
    context_numbers = _numbers_in(context_text)
    context_raw = (context_text or "").replace(",", "")
    failures = []
    for s in _iter_strings(data):
        for num in _numbers_in(s):
            if len(num) < 2:
                continue
            if num not in context_numbers and num not in context_raw:
                failures.append(f"ungrounded number in output: {num}")
    return failures


# --- Public validators -------------------------------------------------------
def validate_rep_brief(data: Dict[str, Any], context_text: str) -> Tuple[bool, List[str]]:
    required = {
        "account_summary": str,
        "key_signals": list,
        "likely_objections": list,
        "next_best_action": str,
        "recommended_talk_track": str,
        "confidence_notes": str,
    }
    failures = _check_required(data, required)
    if not failures:
        failures += _check_strings(data, ["account_summary", "next_best_action"])
        failures += _check_safety(data)
        failures += _check_grounding(data, context_text)
    ok = not failures
    if not ok:
        log_event("guardrail_failure", artifact="rep_brief", failures=failures)
    return ok, failures


def validate_email(data: Dict[str, Any], context_text: str) -> Tuple[bool, List[str]]:
    required = {"subject": str, "body": str, "call_to_action": str}
    failures = _check_required(data, required)
    if not failures:
        failures += _check_strings(data, ["subject", "body", "call_to_action"])
        failures += _check_safety(data)
        failures += _check_grounding(data, context_text)
        # No pricing / contractual commitments in an auto-sent email.
        if _MONEY_RE.search(data.get("body", "")):
            failures.append("email body contains a pricing/dollar commitment")
    ok = not failures
    if not ok:
        log_event("guardrail_failure", artifact="email", failures=failures)
    return ok, failures


def validate_proposal(data: Dict[str, Any], context_text: str = "") -> Tuple[bool, List[str]]:
    required = {"sections": list}
    failures = _check_required(data, required)
    if failures:
        log_event("guardrail_failure", artifact="proposal", failures=failures)
        return False, failures

    valid_ids = content_library_service.valid_block_ids()
    approved_money: Set[str] = set()
    for block in content_library_service.all_blocks():
        for m in _MONEY_RE.findall(block.get("body", "")):
            approved_money.add(m.replace(" ", ""))

    for section in data["sections"]:
        if not isinstance(section, dict):
            failures.append("proposal section is not an object")
            continue
        cited = section.get("content_block_ids", []) or []
        for cid in cited:
            if cid not in valid_ids:
                failures.append(f"fabricated content_block_id: {cid}")
        # Any $-number in section content must trace to an approved block.
        for money in _MONEY_RE.findall(section.get("content", "")):
            if money.replace(" ", "") not in approved_money:
                failures.append(f"unapproved dollar figure in proposal: {money}")

    failures += _check_safety(data)
    ok = not failures
    if not ok:
        log_event("guardrail_failure", artifact="proposal", failures=failures)
    return ok, failures


def validate(artifact_type: str, data: Dict[str, Any], context_text: str = "") -> Tuple[bool, List[str]]:
    if artifact_type == "rep_brief":
        return validate_rep_brief(data, context_text)
    if artifact_type == "email":
        return validate_email(data, context_text)
    if artifact_type == "proposal":
        return validate_proposal(data, context_text)
    return False, [f"unknown artifact type: {artifact_type}"]

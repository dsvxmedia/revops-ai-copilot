"""Approved proposal content-block retrieval by tag/keyword match.

Deliberately NOT embeddings -- a pragmatic tag + keyword scorer over
``data/content_blocks.json``. Every block cited in a proposal must come from
here, which is what the guardrail fabrication check enforces.

See plan section "Generation (3 LLM tasks...)".
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from .. import config

_CACHE: Optional[List[Dict]] = None


def _load_blocks() -> List[Dict]:
    global _CACHE
    if _CACHE is None:
        try:
            with open(config.CONTENT_BLOCKS_PATH, "r", encoding="utf-8") as fh:
                _CACHE = json.load(fh)
        except Exception:  # noqa: BLE001
            _CACHE = []
    return _CACHE


def all_blocks() -> List[Dict]:
    return list(_load_blocks())


def get_block(block_id: str) -> Optional[Dict]:
    for block in _load_blocks():
        if block.get("id") == block_id:
            return block
    return None


def valid_block_ids() -> set:
    return {b.get("id") for b in _load_blocks()}


def search(tags: List[str], keywords: Optional[List[str]] = None, limit: int = 5) -> List[Dict]:
    """Score blocks by tag overlap (weighted) + keyword hits, return top ``limit``."""
    tags_l = {t.lower() for t in (tags or [])}
    keywords_l = [k.lower() for k in (keywords or [])]
    scored = []
    for block in _load_blocks():
        block_tags = {t.lower() for t in block.get("tags", [])}
        score = 3 * len(tags_l & block_tags)
        haystack = f"{block.get('title', '')} {block.get('body', '')}".lower()
        score += sum(1 for k in keywords_l if k in haystack)
        if score > 0:
            scored.append((score, block))
    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    return [b for _, b in scored[:limit]]


def blocks_for_segment(account_type: str) -> List[Dict]:
    """Return an ordered, deduplicated set of blocks appropriate for a proposal.

    Always includes overview/implementation/support/security; adds the
    segment-specific solution block based on the account type.
    """
    type_tag = {
        "Higher Education": "higher-education",
        "K-12": "k-12",
        "Workforce/Corporate Training": "corporate-training",
        "Library/Public Sector": "overview",
    }.get(account_type, "higher-education")

    ordered_tags = ["overview", type_tag, "implementation", "support", "outcomes", "security"]
    picked: List[Dict] = []
    seen = set()
    for tag in ordered_tags:
        for block in search([tag], limit=1):
            if block["id"] not in seen:
                picked.append(block)
                seen.add(block["id"])
    return picked


def pricing_block() -> Optional[Dict]:
    for block in _load_blocks():
        if block.get("contains_pricing"):
            return block
    return None

"""Dual-mode Claude call wrapper.

- Mock mode (no ``ANTHROPIC_API_KEY``): ``generate_json`` returns ``None`` so
  the generation service uses its deterministic template path.
- Live mode: calls the ``anthropic`` SDK with the configured model, parses a
  strict-JSON reply, and (optionally) records an Opik trace. ANY error, timeout,
  missing package, or parse failure returns ``None`` -> template fallback. It
  never raises upward.

See plan sections "Config / Model" and "Observability & Real Enrichment".
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from .. import config
from ..logging_config import log_event


def is_available() -> bool:
    """Live generation requires a key AND an importable anthropic SDK."""
    if not config.is_live_mode():
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _opik_enabled() -> bool:
    if not config.OPIK_API_KEY:
        return False
    try:
        import opik  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _record_trace(task_name: str, meta: Dict[str, Any]) -> None:
    """Best-effort Opik trace. Guarded so its absence never breaks anything."""
    if not _opik_enabled():
        return
    try:  # pragma: no cover - exercised only with opik installed + configured
        import opik

        client = opik.Opik()
        trace = client.trace(name=f"revops.generate.{task_name}", metadata=meta)
        try:
            trace.end()
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        log_event("opik_trace_skipped", task=task_name, reason=str(exc)[:160])


def _extract_text(message: Any) -> str:
    try:
        parts = []
        for block in message.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()
    except Exception:  # noqa: BLE001
        return ""


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    # Grab the outermost JSON object if there's surrounding prose.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        return json.loads(cleaned)
    except Exception:  # noqa: BLE001
        return None


def generate_json(
    system_prompt: str, user_content: str, task_name: str
) -> Optional[Dict[str, Any]]:
    """Call Claude for strict JSON. Returns ``None`` on any failure (-> fallback)."""
    if not is_available():
        return None

    started = time.time()
    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=config.ANTHROPIC_API_KEY, timeout=config.LLM_TIMEOUT_SECONDS
        )
        message = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        text = _extract_text(message)
        data = _parse_json(text)
        elapsed = time.time() - started

        usage = getattr(message, "usage", None)
        meta = {
            "task": task_name,
            "model": config.ANTHROPIC_MODEL,
            "latency_s": round(elapsed, 3),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "parsed_ok": data is not None,
        }
        _record_trace(task_name, meta)
        log_event("llm_call", **meta)

        if data is None:
            log_event("llm_parse_failure", task=task_name)
        return data
    except Exception as exc:  # noqa: BLE001 - fall back to templates, never crash
        log_event(
            "llm_call_error",
            task=task_name,
            reason=str(exc)[:200],
            latency_s=round(time.time() - started, 3),
        )
        return None

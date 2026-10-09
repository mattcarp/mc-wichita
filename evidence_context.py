"""
Lightweight evidence helpers for alert review endpoints.
Dashboard v2 uses the capture feed; these remain for legacy alert routes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _parse_observed_at(alert: Any) -> Optional[datetime]:
    meta = getattr(alert, "metadata", None) or {}
    if isinstance(meta, dict):
        raw = meta.get("observed_at") or meta.get("capture_time")
        if raw:
            if isinstance(raw, datetime):
                return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                return None
    created = getattr(alert, "created_at", None)
    if isinstance(created, datetime):
        return created if created.tzinfo else created.replace(tzinfo=timezone.utc)
    return None


def evidence_context(alert: Any) -> Dict[str, Any]:
    observed = _parse_observed_at(alert)
    now = datetime.now(timezone.utc)
    age_seconds: Optional[float] = None
    if observed:
        age_seconds = max(0.0, (now - observed).total_seconds())
    meta = getattr(alert, "metadata", None) or {}
    unknown_fields = meta.get("unknown_fields") or meta.get("missing_fields") or []
    return {
        "alert_id": getattr(alert, "id", None),
        "observed_at": observed.isoformat() if observed else None,
        "age_seconds": age_seconds,
        "provenance_status": meta.get("provenance_status", "unverified"),
        "unknown_fields": list(unknown_fields) if isinstance(unknown_fields, list) else [],
        "title": getattr(alert, "title", None),
        "summary": getattr(alert, "message", None) or getattr(alert, "summary", None),
    }


def answer_question(alert: Any, question: str) -> Dict[str, Any]:
    ctx = evidence_context(alert)
    q = (question or "").strip().lower()
    if q in {"when", "time", "observed"}:
        return {"question": question, "answer": ctx.get("observed_at"), "fields_used": ["observed_at"]}
    if q in {"provenance", "source"}:
        return {
            "question": question,
            "answer": ctx.get("provenance_status"),
            "fields_used": ["provenance_status"],
        }
    return {
        "question": question,
        "answer": "Only recorded alert fields are available; no inference performed.",
        "fields_used": list(ctx.keys()),
    }


def delivery_health(captures: List[Any], alerts: List[Any]) -> Dict[str, Any]:
    return {
        "captures_in_memory": len(captures),
        "alerts_in_memory": len(alerts),
        "status": "ok",
        "note": "Live capture feed uses WICHITA_CAPTURES_DIRS; in-memory captures are legacy.",
    }

"""
Evidence context helpers for the Wichita dashboard and /alerts/{id}/evidence API.

Answers and ages are derived from recorded fields only; nothing is inferred beyond
parsing explicit ISO timestamps in metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

MALTA_TZ_NAME = "Europe/Malta"

RecordLike = Union[Any, Dict[str, Any]]


def _as_dict(record: RecordLike) -> Dict[str, Any]:
    if isinstance(record, dict):
        return record
    if hasattr(record, "model_dump"):
        return record.model_dump()
    if hasattr(record, "dict"):
        return record.dict()
    raise TypeError(f"Unsupported record type: {type(record)!r}")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_aware(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _ensure_aware(parsed)


def _metadata(record: RecordLike) -> Dict[str, Any]:
    data = _as_dict(record)
    meta = data.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def observed_at_from_record(record: RecordLike) -> Optional[datetime]:
    """Return metadata.observed_at when present and timezone-aware (or UTC-normalised)."""
    meta = _metadata(record)
    return _parse_datetime(meta.get("observed_at"))


def provenance_status_from_record(record: RecordLike) -> Optional[str]:
    meta = _metadata(record)
    status = meta.get("provenance_status") or meta.get("wichita:provenance_status")
    if status is None:
        return None
    return str(status)


def missing_provenance_fields(record: RecordLike) -> List[str]:
    meta = _metadata(record)
    explicit = meta.get("provenance_missing_fields") or meta.get("missing_provenance_fields")
    if isinstance(explicit, list):
        return [str(item) for item in explicit]
    missing: List[str] = []
    if not observed_at_from_record(record):
        missing.append("observed_at")
    if not provenance_status_from_record(record):
        missing.append("provenance_status")
    if not meta.get("analysis_method") and not meta.get("wichita:method"):
        missing.append("analysis_method")
    if not meta.get("audio_sha256") and not meta.get("wichita:audio_sha256"):
        missing.append("audio_sha256")
    return missing


def age_seconds(observed_at: Optional[datetime], now: Optional[datetime] = None) -> Optional[float]:
    if observed_at is None:
        return None
    reference = now or datetime.now(timezone.utc)
    return (reference - _ensure_aware(observed_at)).total_seconds()


def evidence_context(record: RecordLike) -> Dict[str, Any]:
    data = _as_dict(record)
    observed = observed_at_from_record(record)
    created = _parse_datetime(data.get("created_at"))
    meta = _metadata(record)
    status = provenance_status_from_record(record)
    missing = missing_provenance_fields(record)
    unknowns = meta.get("provenance_unknowns")
    if not isinstance(unknowns, list):
        unknowns = [field for field in missing]

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "source": data.get("source"),
        "created_at": created.isoformat() if created else None,
        "observed_at": observed.isoformat() if observed else None,
        "has_observation_time": observed is not None,
        "age_seconds": age_seconds(observed),
        "provenance_status": status,
        "provenance_missing_fields": missing,
        "provenance_unknowns": unknowns,
        "audio_url": data.get("audio_url"),
        "frequency_mhz": data.get("frequency_mhz"),
        "language": data.get("language"),
        "transcript": data.get("transcript"),
        "metadata": meta,
    }


def _summarise_source(
    source_key: str,
    records: Sequence[RecordLike],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    reference = now or datetime.now(timezone.utc)
    latest_observed: Optional[datetime] = None
    latest_created: Optional[datetime] = None
    for record in records:
        data = _as_dict(record)
        if data.get("source") != source_key:
            continue
        observed = observed_at_from_record(record)
        created = _parse_datetime(data.get("created_at"))
        if observed and (latest_observed is None or observed > latest_observed):
            latest_observed = observed
        if created and (latest_created is None or created > latest_created):
            latest_created = created

    anchor = latest_observed or latest_created
    return {
        "source": source_key,
        "record_count": sum(1 for r in records if _as_dict(r).get("source") == source_key),
        "last_observed_at": latest_observed.isoformat() if latest_observed else None,
        "last_created_at": latest_created.isoformat() if latest_created else None,
        "age_seconds": age_seconds(anchor, reference) if anchor else None,
        "has_observation_time": latest_observed is not None,
    }


def delivery_health(
    captures: Sequence[RecordLike],
    alerts: Sequence[RecordLike],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    sources = sorted(
        {
            _as_dict(item).get("source")
            for item in list(captures) + list(alerts)
            if _as_dict(item).get("source")
        }
    )
    return {
        "sources": [_summarise_source(source, list(captures) + list(alerts), now=now) for source in sources],
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
    }


def answer_question(record: RecordLike, question: str) -> Dict[str, Any]:
    q = (question or "").strip().lower()
    if not q:
        raise ValueError("question must not be empty")

    ctx = evidence_context(record)
    if "when" in q and ("observ" in q or "heard" in q or "recorded" in q):
        if ctx["observed_at"]:
            return {"question": question, "answer": ctx["observed_at"], "field": "observed_at"}
        return {
            "question": question,
            "answer": None,
            "field": "observed_at",
            "note": "No observation time is recorded for this event.",
        }
    if "source" in q:
        return {"question": question, "answer": ctx.get("source"), "field": "source"}
    if "provenance" in q or "genuine" in q or "verified" in q:
        return {
            "question": question,
            "answer": ctx.get("provenance_status"),
            "field": "provenance_status",
            "missing_fields": ctx.get("provenance_missing_fields"),
        }
    if "language" in q:
        return {"question": question, "answer": ctx.get("language"), "field": "language"}
    if "frequency" in q:
        return {"question": question, "answer": ctx.get("frequency_mhz"), "field": "frequency_mhz"}
    if "age" in q or "how old" in q:
        if ctx["age_seconds"] is not None:
            return {"question": question, "answer": ctx["age_seconds"], "field": "age_seconds"}
        return {
            "question": question,
            "answer": None,
            "field": "age_seconds",
            "note": "Age requires a recorded observation time.",
        }

    raise ValueError(f"Unsupported question: {question}")

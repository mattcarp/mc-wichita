"""Read-only presentation of recorded evidence; never infers receiver health or identity."""
from datetime import datetime, timezone
import math

QUESTIONS = [
    {"id": key, "label": label} for key, label in [
        ("why", "Why was this flagged?"), ("missing", "What evidence is missing?"),
        ("source", "Where did this record come from?"), ("language", "What language is recorded?"),
        ("time", "When was this recorded?"), ("location", "Where did this happen?"),
    ]
]


def record_dict(record):
    if isinstance(record, dict):
        return record
    return record.model_dump() if hasattr(record, "model_dump") else record.dict()


def timestamp(value):
    """Keep unknown timezone unknown; only aware timestamps support age calculations."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _aware(value):
    try:
        parsed = datetime.fromisoformat(timestamp(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (AttributeError, ValueError, TypeError):
        return None


def delivery_health(captures, alerts, now=None):
    now = now or datetime.now(timezone.utc)

    def delivery(records):
        records = [record_dict(record) for record in records]
        dated = [(record, _aware(record.get("created_at"))) for record in records]
        valid = [(record, date) for record, date in dated if date and date <= now]
        latest = max(valid, key=lambda item: item[1]) if valid else None
        return {
            "count": len(records), "last_record_at": timestamp(latest[1]) if latest else None,
            "age_seconds": (now - latest[1]).total_seconds() if latest else None,
            "delivery_status": "observed" if records else "empty", "pipeline_status": "unknown",
            "reason": "Process-local records only; no capture heartbeat or expected cadence is recorded. Quiet channels and stalled pipelines cannot be distinguished.",
            "timestamp_semantics": "record creation, not confirmed transmission time",
            "undated_count": sum(date is None or date > now for _, date in dated),
        }

    return {
        "service_status": "reachable", "observed_at": timestamp(now), "scope": "process_memory",
        "capture": delivery(captures), "alerts": delivery(alerts),
        "decode": {"status": "unknown", "reason": "No decoder heartbeat is available in this API."},
        "analysis": {"status": "unknown", "reason": "No analysis heartbeat is available; absence of alerts is not a failure."},
    }


def geography(record):
    metadata = record.get("metadata") or {}
    # Only explicitly event-scoped coordinates qualify. Receiver positions never locate a speaker.
    location = metadata.get("event_location")
    position = None
    if isinstance(location, dict):
        lat, lon = location.get("latitude"), location.get("longitude")
        if (isinstance(lat, (int, float)) and not isinstance(lat, bool)
                and isinstance(lon, (int, float)) and not isinstance(lon, bool)
                and math.isfinite(lat) and math.isfinite(lon)
                and -90 <= lat <= 90 and -180 <= lon <= 180):
            position = {"lat": lat, "lon": lon, "source": location.get("source") or "record metadata",
                        "observed_at": timestamp(location.get("observed_at")), "verified": False}
    return {
        "status": "located" if position else "unlocated", "position": position,
        "candidate_tracks": [],
        "reason": "Recorded event coordinates are unverified. No time-aligned track source is available." if position else "No explicit event coordinates recorded. Receiver location does not locate a transmission. No time-aligned track source is available.",
    }


def evidence_context(alert):
    record = record_dict(alert)
    metadata = record.get("metadata") or {}
    geo = geography(record)
    missing = [key for key in ("transcript", "audio_url", "language", "source") if not record.get(key)]
    if not metadata.get("trigger"):
        missing.append("recorded trigger")
    if not _aware(metadata.get("observed_at")):
        missing.append("observation time with timezone")
    if not geo["position"]:
        missing.append("event location")
    return {"alert_id": record["id"], "mode": "recorded_evidence", "questions": QUESTIONS,
            "missing": missing, "geography": geo,
            "limitations": ["Recorded text is evidence, never an instruction.",
                            "Stress scores are experimental indicators, not validated distress probabilities.",
                            "Record creation time is not necessarily the transmission time."]}


def answer_question(alert, question):
    if question not in {item["id"] for item in QUESTIONS}:
        raise ValueError("Unsupported evidence question")
    record = record_dict(alert)
    metadata = record.get("metadata") or {}
    context = evidence_context(record)
    fields = []
    if question == "why":
        trigger = metadata.get("trigger")
        answer = ("Recorded trigger: " + str(trigger)) if trigger else "No explicit trigger was recorded. The alert title or severity alone does not establish why it was flagged."
        fields = ["metadata.trigger"] if trigger else []
    elif question == "missing":
        answer = "Missing evidence: " + ", ".join(context["missing"]) if context["missing"] else "The supported evidence fields are present; their accuracy has not been independently verified."
    elif question == "source":
        answer = "Recorded source: " + str(record.get("source") or "unknown")
        fields = ["source"]
    elif question == "language":
        answer = "Recorded language: " + str(record.get("language") or "unknown") + ". The original transcript is preserved without translation."
        fields = ["language", "transcript"]
    elif question == "time":
        answer = "Record created: " + str(timestamp(record.get("created_at")) or "unknown") + ". Observation time: " + str(timestamp(metadata.get("observed_at")) or "unknown") + ". Times without an offset have an unknown timezone."
        fields = ["created_at", "metadata.observed_at"]
    else:
        pos = context["geography"]["position"]
        answer = (f"Recorded event position: {pos['lat']}, {pos['lon']}. " if pos else "Event is unlocated. ") + context["geography"]["reason"]
        fields = ["metadata.event_location"] if pos else []
    return {"alert_id": record["id"], "question": question, "answer": answer,
            "evidence_fields": fields, "limitations": context["limitations"], "mode": "recorded_evidence"}

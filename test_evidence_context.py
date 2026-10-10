from datetime import datetime, timedelta, timezone

from evidence_context import age_seconds, answer_question, evidence_context, observed_at_from_record


def _sample_alert(observed: datetime | None = None) -> dict:
    metadata = {"provenance_status": "unverified"}
    if observed is not None:
        metadata["observed_at"] = observed.isoformat()
    return {
        "id": "alert-1",
        "created_at": datetime.now(timezone.utc),
        "title": "Test alert",
        "description": None,
        "signal_type": "unknown",
        "severity": "info",
        "frequency_mhz": 156.8,
        "confidence": 0.5,
        "transcript": None,
        "language": "en",
        "audio_url": "/api/audio/sample.wav",
        "tags": [],
        "metadata": metadata,
        "source": "wichita-sdr",
    }


def test_evidence_context_reports_age_when_observed_at_present() -> None:
    observed = datetime.now(timezone.utc) - timedelta(minutes=5)
    ctx = evidence_context(_sample_alert(observed))
    assert ctx["has_observation_time"] is True
    assert ctx["age_seconds"] is not None
    assert ctx["age_seconds"] >= 299


def test_evidence_context_marks_missing_observation_time() -> None:
    ctx = evidence_context(_sample_alert(None))
    assert ctx["has_observation_time"] is False
    assert ctx["age_seconds"] is None
    assert "observed_at" in ctx["provenance_missing_fields"]


def test_answer_question_when_observed() -> None:
    observed = datetime(2025, 9, 12, 17, 46, 56, tzinfo=timezone.utc)
    answer = answer_question(_sample_alert(observed), "When was this observed?")
    assert answer["field"] == "observed_at"
    assert answer["answer"] is not None


def test_age_seconds_helper() -> None:
    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    observed = now - timedelta(seconds=42)
    assert age_seconds(observed, now=now) == 42.0


def test_observed_at_from_record_parses_z_suffix() -> None:
    record = _sample_alert(None)
    record["metadata"]["observed_at"] = "2025-09-12T19:46:56Z"
    parsed = observed_at_from_record(record)
    assert parsed is not None
    assert parsed.tzinfo is not None

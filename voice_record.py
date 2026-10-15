"""
Voice evidence record: one received transmission, ready for the human review queue.

Voice path task 2 (openspec/changes/voice-path). Builds an AlertRecord-shaped dict
from a demodulated clip plus what is actually known about it, writes the SigMF-shaped
provenance sidecar beside the clip, and persists through alert_store so the record
survives restarts and appears in the existing review queue.

Rules:
- Times must be timezone-aware. A naive datetime is refused, never guessed.
- Anything not supplied is None and listed in metadata["unknown_fields"].
- A transcript the model is unsure of is kept and tagged, never dropped.
- Nothing here dispatches alerts; review_status defaults to pending_review in the API.
"""

from __future__ import annotations

import uuid
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import alert_store
from capture_provenance import ProvenanceStatus, WICHITA_SOURCE, write_sidecar

MODES = frozenset({"am", "nfm", "usb", "lsb"})
TRANSCRIPT_UNSURE_BELOW = 0.6
RECORD_KIND = "voice_transmission"

# Optional fields: when not supplied they are listed as unknown, never filled in.
OPTIONAL_FIELDS = (
    "receiver",
    "signal_dbfs",
    "transcript",
    "language",
    "language_confidence",
    "transcript_confidence",
    "scores",
    "trigger",
)


class VoiceRecordError(ValueError):
    """The inputs cannot form a truthful record."""


def _require_aware(name: str, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise VoiceRecordError(f"{name} must be timezone-aware, got naive {value!r}")
    return value.astimezone(timezone.utc)


def wav_duration_sec(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def signal_type_for(frequency_mhz: float) -> str:
    """Map a frequency to an existing api_server.SignalType value."""
    f = round(frequency_mhz, 4)
    if f in (121.5, 243.0):
        return "emergency"
    if 156.0 <= f <= 162.025:
        return "marine_vhf"
    if 144.0 <= f <= 146.0 or 430.0 <= f <= 440.0:
        return "amateur"
    return "unknown"


def build_voice_record(
    audio_path: Path,
    *,
    frequency_mhz: float,
    mode: str,
    observed_start: datetime,
    observed_end: Optional[datetime] = None,
    provenance_status: ProvenanceStatus = ProvenanceStatus.UNVERIFIED,
    hw: str = "unknown",
    receiver: Optional[str] = None,
    signal_dbfs: Optional[float] = None,
    transcript: Optional[str] = None,
    language: Optional[str] = None,
    language_confidence: Optional[float] = None,
    transcript_confidence: Optional[float] = None,
    scores: Optional[Dict[str, float]] = None,
    trigger: Optional[Dict[str, Any]] = None,
    audio_url: Optional[str] = None,
    ingested_at: Optional[datetime] = None,
    write_provenance: bool = True,
) -> Dict[str, Any]:
    audio_path = Path(audio_path).resolve()
    if not audio_path.is_file():
        raise VoiceRecordError(f"audio not found: {audio_path}")
    mode = mode.lower()
    if mode not in MODES:
        raise VoiceRecordError(f"mode must be one of {sorted(MODES)}, got {mode!r}")

    start = _require_aware("observed_start", observed_start)
    duration = wav_duration_sec(audio_path)
    if observed_end is None:
        end = start + timedelta(seconds=duration)
        end_source = "start_plus_clip_duration"
    else:
        end = _require_aware("observed_end", observed_end)
        end_source = "supplied"
        if end < start:
            raise VoiceRecordError("observed_end is before observed_start")
    ingested = _require_aware("ingested_at", ingested_at) if ingested_at else datetime.now(timezone.utc)

    supplied = {
        "receiver": receiver,
        "signal_dbfs": signal_dbfs,
        "transcript": transcript,
        "language": language,
        "language_confidence": language_confidence,
        "transcript_confidence": transcript_confidence,
        "scores": scores,
        "trigger": trigger,
    }
    unknown: List[str] = [k for k in OPTIONAL_FIELDS if supplied[k] is None]

    sidecar = None
    if write_provenance:
        sidecar = write_sidecar(
            audio_path,
            frequency_hz=int(round(frequency_mhz * 1_000_000)),
            provenance_status=provenance_status,
            observation_time=start,
            hw=hw,
            method=f"{mode} demod, voice_record",
            tool="voice_record.py",
        )

    tags = [RECORD_KIND, f"mode:{mode}", f"provenance:{provenance_status.value}"]
    if provenance_status is not ProvenanceStatus.GENUINE:
        tags.append("not-established-genuine")
    if transcript is not None and (
        transcript_confidence is None or transcript_confidence < TRANSCRIPT_UNSURE_BELOW
    ):
        tags.append("transcript:unsure")

    top_score = max(scores.values()) if scores else None
    title = f"Voice on {frequency_mhz:.4f} MHz ({mode.upper()})"

    return {
        "id": str(uuid.uuid4()),
        "created_at": ingested,
        "title": title,
        "description": transcript,
        "signal_type": signal_type_for(frequency_mhz),
        "severity": "info",
        "frequency_mhz": frequency_mhz,
        "confidence": float(top_score) if top_score is not None else 0.0,
        "transcript": transcript,
        "language": language,
        "audio_url": audio_url or f"/api/audio/{audio_path.name}",
        "tags": tags,
        "source": WICHITA_SOURCE,
        "metadata": {
            "record_kind": RECORD_KIND,
            "audio_file": str(audio_path),
            "sidecar_path": str(sidecar) if sidecar else None,
            "mode": mode,
            "observed_start_utc": start.isoformat(),
            "observed_end_utc": end.isoformat(),
            "observed_end_source": end_source,
            "ingested_at_utc": ingested.isoformat(),
            "clip_duration_sec": round(duration, 3),
            "provenance_status": provenance_status.value,
            "receiver": receiver,
            "hw": hw,
            "signal_dbfs": signal_dbfs,
            "language_confidence": language_confidence,
            "transcript_confidence": transcript_confidence,
            "scores": scores,
            "trigger": trigger,
            "unknown_fields": unknown,
        },
    }


def persist_voice_record(record: Dict[str, Any]) -> None:
    """Append to the review queue store (alert_store JSONL)."""
    if (record.get("metadata") or {}).get("record_kind") != RECORD_KIND:
        raise VoiceRecordError("not a voice record")
    alert_store.append_alert_record(record)

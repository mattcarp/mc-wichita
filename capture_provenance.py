"""
SigMF-shaped capture provenance sidecars and a read-only import path into ALERTS.

No alert dispatch, no hardware access. Synthetic test WAVs are fine in unit tests
when labelled synthetic and never marked genuine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import uuid
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Frequencies referenced by the REAL_RTL_CAPTURE regression set (MHz at module scope).
FM_BROADCAST_TEST_MHZ = 88.5
MARITIME_CH09_MHZ = 156.45
MARITIME_CH16_MHZ = 156.8

MALTA_TZ = ZoneInfo("Europe/Malta")
WICHITA_SOURCE = "wichita-sdr"
DEFAULT_TOOL = "rtl_sdr_real_capture.py"
DEFAULT_METHOD = "rtl_fm demod, 48 kHz mono, normalised 0.7"
SIGMF_VERSION = "1.0.0"
SIDECAR_SUFFIX = ".sigmf-meta"

_FILENAME_STAMP_RE = re.compile(
    r"REAL_RTL_CAPTURE_.+?_(\d+(?:\.\d+)?)MHz_(\d{8})_(\d{6})\.wav$",
    re.IGNORECASE,
)


class ProvenanceStatus(str, Enum):
    GENUINE = "genuine"
    SYNTHETIC = "synthetic"
    UNVERIFIED = "unverified"


class ProvenanceError(Exception):
    """Base class for provenance validation failures."""


class ProvenanceImportError(ProvenanceError):
    """Import cannot proceed (malformed sidecar, hash mismatch, etc.)."""


@dataclass
class SidecarReadResult:
    path: Optional[Path]
    document: Optional[Dict[str, Any]]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ImportResult:
    """AlertRecord-shaped dict ready for api_server.AlertRecord(**data)."""

    id: str
    created_at: datetime
    title: str
    description: Optional[str]
    signal_type: str
    severity: str
    frequency_mhz: Optional[float]
    confidence: float
    transcript: Optional[str]
    language: Optional[str]
    audio_url: Optional[str]
    tags: List[str]
    metadata: Dict[str, Any]
    source: str

    def as_alert_kwargs(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "title": self.title,
            "description": self.description,
            "signal_type": self.signal_type,
            "severity": self.severity,
            "frequency_mhz": self.frequency_mhz,
            "confidence": self.confidence,
            "transcript": self.transcript,
            "language": self.language,
            "audio_url": self.audio_url,
            "tags": self.tags,
            "metadata": self.metadata,
            "source": self.source,
        }


def sidecar_path_for(audio_path: Path) -> Path:
    return audio_path.with_name(audio_path.name + SIDECAR_SUFFIX)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _mhz_to_hz(mhz: float) -> int:
    return int(round(mhz * 1_000_000))


def observation_time_from_filename(filename: str) -> Optional[datetime]:
    match = _FILENAME_STAMP_RE.match(filename)
    if not match:
        return None
    date_part, time_part = match.group(2), match.group(3)
    naive = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
    return naive.replace(tzinfo=MALTA_TZ)


def frequency_mhz_from_filename(filename: str) -> Optional[float]:
    match = _FILENAME_STAMP_RE.match(filename)
    if not match:
        return None
    return float(match.group(1))


def build_sigmf_document(
    audio_path: Path,
    *,
    frequency_hz: int,
    provenance_status: ProvenanceStatus,
    observation_time: Optional[datetime],
    sample_rate_hz: int = 48000,
    hw: str = "RTL-SDR Blog V3, gain 40 dB",
    author: str = "Matt Carpenter",
    method: str = DEFAULT_METHOD,
    tool: str = DEFAULT_TOOL,
    audio_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    if audio_sha256 is None:
        audio_sha256 = sha256_file(audio_path)

    global_obj: Dict[str, Any] = {
        "core:datatype": "ci16_le",
        "core:sample_rate": sample_rate_hz,
        "core:version": SIGMF_VERSION,
        "core:hw": hw,
        "core:author": author,
        "wichita:source": WICHITA_SOURCE,
        "wichita:frequency_hz": frequency_hz,
        "wichita:provenance_status": provenance_status.value,
        "wichita:method": method,
        "wichita:tool": tool,
        "wichita:audio_sha256": audio_sha256,
        "wichita:recording_kind": "demod_audio_wav",
    }

    captures: List[Dict[str, Any]] = []
    if observation_time is not None:
        captures.append(
            {
                "core:sample_start": 0,
                "core:frequency": frequency_hz,
                "core:datetime": observation_time.astimezone(MALTA_TZ).isoformat(),
            }
        )

    return {"global": global_obj, "captures": captures, "annotations": []}


def write_sidecar(
    audio_path: Path,
    *,
    frequency_hz: int,
    provenance_status: ProvenanceStatus = ProvenanceStatus.UNVERIFIED,
    observation_time: Optional[datetime] = None,
    sample_rate_hz: int = 48000,
    hw: str = "RTL-SDR Blog V3, gain 40 dB",
    author: str = "Matt Carpenter",
    method: str = DEFAULT_METHOD,
    tool: str = DEFAULT_TOOL,
) -> Path:
    audio_path = audio_path.resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    document = build_sigmf_document(
        audio_path,
        frequency_hz=frequency_hz,
        provenance_status=provenance_status,
        observation_time=observation_time,
        sample_rate_hz=sample_rate_hz,
        hw=hw,
        author=author,
        method=method,
        tool=tool,
    )
    sidecar = sidecar_path_for(audio_path)
    sidecar.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote provenance sidecar %s", sidecar)
    return sidecar


def read_sidecar(audio_path: Path) -> SidecarReadResult:
    sidecar = sidecar_path_for(audio_path)
    if not sidecar.is_file():
        return SidecarReadResult(path=None, document=None, errors=["missing_sidecar"])

    try:
        document = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return SidecarReadResult(path=sidecar, document=None, errors=[f"invalid_json: {exc}"])

    if not isinstance(document, dict) or "global" not in document:
        return SidecarReadResult(
            path=sidecar,
            document=None,
            errors=["invalid_sigmf_shape: expected object with global"],
        )

    return SidecarReadResult(path=sidecar, document=document)


def _global_field(document: Dict[str, Any], key: str) -> Any:
    global_obj = document.get("global") or {}
    return global_obj.get(key) or global_obj.get(f"wichita:{key}")


def validate_sidecar_against_audio(
    audio_path: Path,
    document: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    expected_hash = _global_field(document, "audio_sha256")
    if not expected_hash:
        errors.append("missing_wichita:audio_sha256")
    else:
        actual = sha256_file(audio_path)
        if actual.lower() != str(expected_hash).lower():
            errors.append("audio_sha256_mismatch")

    status = _global_field(document, "provenance_status")
    if status not in {item.value for item in ProvenanceStatus}:
        errors.append("invalid_provenance_status")

    return errors, warnings


def _observation_from_document(document: Dict[str, Any]) -> Optional[datetime]:
    captures = document.get("captures") or []
    if not captures:
        return None
    first = captures[0] if isinstance(captures[0], dict) else {}
    raw = first.get("core:datetime")
    if not raw:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=MALTA_TZ)
    return parsed


def _missing_fields_without_sidecar() -> List[str]:
    return [
        "sidecar",
        "wichita:audio_sha256",
        "wichita:method",
        "wichita:tool",
        "core:datetime",
        "provenance_status",
    ]


def _unknowns_for_status(status: str, missing: List[str]) -> List[str]:
    unknowns: List[str] = list(missing)
    if status != ProvenanceStatus.GENUINE.value:
        unknowns.append("off_air_authenticity")
    return sorted(set(unknowns))


def import_capture(
    audio_path: Path,
    *,
    title: Optional[str] = None,
    audio_url: Optional[str] = None,
) -> ImportResult:
    """
    Build an AlertRecord-shaped import from audio + optional SigMF sidecar.

    Missing sidecar: unverified with explicit missing fields (not treated as genuine).
    Malformed sidecar or hash mismatch: raises ProvenanceImportError.
    """
    audio_path = audio_path.resolve()
    if not audio_path.is_file():
        raise ProvenanceImportError(f"Audio file not found: {audio_path}")

    read_result = read_sidecar(audio_path)
    if read_result.errors:
        if read_result.errors == ["missing_sidecar"]:
            status = ProvenanceStatus.UNVERIFIED.value
            missing = _missing_fields_without_sidecar()
            freq_mhz = frequency_mhz_from_filename(audio_path.name)
            metadata = {
                "provenance_status": status,
                "provenance_missing_fields": missing,
                "provenance_unknowns": _unknowns_for_status(status, missing),
                "audio_file": str(audio_path),
                "import_note": "No SigMF sidecar; not treated as verified capture.",
            }
            return ImportResult(
                id=str(uuid.uuid4()),
                created_at=datetime.now(timezone.utc),
                title=title or f"Imported capture (no sidecar): {audio_path.name}",
                description="Capture imported without provenance sidecar.",
                signal_type="unknown",
                severity="info",
                frequency_mhz=freq_mhz,
                confidence=0.0,
                transcript=None,
                language=None,
                audio_url=audio_url or f"/api/audio/{audio_path.name}",
                tags=["import", "provenance:unverified", "not-established-genuine"],
                metadata=metadata,
                source=WICHITA_SOURCE,
            )

        raise ProvenanceImportError(
            "Sidecar rejected: " + "; ".join(read_result.errors)
        )

    document = read_result.document or {}
    validation_errors, _warnings = validate_sidecar_against_audio(audio_path, document)
    if validation_errors:
        raise ProvenanceImportError(
            "Sidecar validation failed: " + "; ".join(validation_errors)
        )

    global_obj = document.get("global") or {}
    status = str(
        global_obj.get("wichita:provenance_status")
        or global_obj.get("provenance_status")
        or ProvenanceStatus.UNVERIFIED.value
    )
    if status not in {item.value for item in ProvenanceStatus}:
        raise ProvenanceImportError(f"Invalid provenance_status: {status}")

    observed = _observation_from_document(document)
    freq_hz = global_obj.get("wichita:frequency_hz")
    freq_mhz = float(freq_hz) / 1_000_000 if freq_hz else frequency_mhz_from_filename(audio_path.name)

    missing: List[str] = []
    if observed is None:
        missing.append("core:datetime")
    if not global_obj.get("wichita:method"):
        missing.append("wichita:method")

    metadata = {
        "provenance_status": status,
        "provenance_missing_fields": missing,
        "provenance_unknowns": _unknowns_for_status(status, missing),
        "observed_at": observed.astimezone(timezone.utc).isoformat() if observed else None,
        "analysis_method": global_obj.get("wichita:method"),
        "audio_sha256": global_obj.get("wichita:audio_sha256"),
        "audio_file": str(audio_path),
        "wichita:tool": global_obj.get("wichita:tool"),
        "wichita:hw": global_obj.get("core:hw"),
        "sidecar_path": str(read_result.path) if read_result.path else None,
    }

    tags = ["import", f"provenance:{status}"]
    if status != ProvenanceStatus.GENUINE.value:
        tags.append("not-established-genuine")

    return ImportResult(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        title=title or f"Imported capture: {audio_path.name}",
        description=global_obj.get("wichita:method"),
        signal_type="unknown",
        severity="info",
        frequency_mhz=freq_mhz,
        confidence=0.0,
        transcript=None,
        language=None,
        audio_url=audio_url or f"/api/audio/{audio_path.name}",
        tags=tags,
        metadata=metadata,
        source=str(global_obj.get("wichita:source") or WICHITA_SOURCE),
    )


def attach_sidecar_retro(
    audio_path: Path,
    *,
    provenance_status: ProvenanceStatus = ProvenanceStatus.UNVERIFIED,
    frequency_mhz: Optional[float] = None,
    include_observation_from_filename: bool = False,
) -> Path:
    """
    Create a sidecar for an existing WAV on disk without claiming off-air authenticity.

    By default observation time is omitted (unknown). Pass include_observation_from_filename=True
    only when the filename stamp is trusted as Europe/Malta local time.
    """
    audio_path = audio_path.resolve()
    freq_mhz = frequency_mhz or frequency_mhz_from_filename(audio_path.name)
    if freq_mhz is None:
        raise ProvenanceError("frequency_mhz is required when it cannot be parsed from filename")

    observation: Optional[datetime] = None
    if include_observation_from_filename:
        observation = observation_time_from_filename(audio_path.name)

    return write_sidecar(
        audio_path,
        frequency_hz=_mhz_to_hz(freq_mhz),
        provenance_status=provenance_status,
        observation_time=observation,
    )


def _write_synthetic_wav(path: Path, sample_rate: int = 48000, seconds: float = 0.05) -> None:
    """Test helper: tiny labelled synthetic PCM WAV (not real RF)."""
    import struct

    frames = int(sample_rate * seconds)
    samples = [int(1000 * (i % 50)) for i in range(frames)]
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def _cli_attach(args: argparse.Namespace) -> int:
    status = ProvenanceStatus(args.status)
    path = Path(args.audio)
    attach_sidecar_retro(
        path,
        provenance_status=status,
        frequency_mhz=args.frequency_mhz,
        include_observation_from_filename=args.trust_filename_time,
    )
    print(sidecar_path_for(path))
    return 0


def _cli_import(args: argparse.Namespace) -> int:
    result = import_capture(Path(args.audio))
    print(json.dumps(result.as_alert_kwargs(), indent=2, default=str))
    return 0


def _cli_write(args: argparse.Namespace) -> int:
    path = Path(args.audio)
    observation = None
    if args.trust_filename_time:
        observation = observation_time_from_filename(path.name)
    write_sidecar(
        path,
        frequency_hz=_mhz_to_hz(args.frequency_mhz),
        provenance_status=ProvenanceStatus(args.status),
        observation_time=observation,
    )
    print(sidecar_path_for(path))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Wichita capture provenance sidecars")
    sub = parser.add_subparsers(dest="command", required=True)

    attach = sub.add_parser("attach", help="Retro-fit sidecar for an existing WAV")
    attach.add_argument("audio", type=str)
    attach.add_argument(
        "--status",
        choices=[s.value for s in ProvenanceStatus],
        default=ProvenanceStatus.UNVERIFIED.value,
    )
    attach.add_argument("--frequency-mhz", type=float, default=None)
    attach.add_argument(
        "--trust-filename-time",
        action="store_true",
        help="Set core:datetime from REAL_RTL_CAPTURE_* filename (Malta local); default omits it",
    )
    attach.set_defaults(func=_cli_attach)

    import_cmd = sub.add_parser("import", help="Validate and emit AlertRecord JSON (no dispatch)")
    import_cmd.add_argument("audio", type=str)
    import_cmd.set_defaults(func=_cli_import)

    write_cmd = sub.add_parser("write", help="Write sidecar for an existing WAV")
    write_cmd.add_argument("audio", type=str)
    write_cmd.add_argument("--frequency-mhz", type=float, required=True)
    write_cmd.add_argument(
        "--status",
        choices=[s.value for s in ProvenanceStatus],
        default=ProvenanceStatus.UNVERIFIED.value,
    )
    write_cmd.add_argument("--trust-filename-time", action="store_true")
    write_cmd.set_defaults(func=_cli_write)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

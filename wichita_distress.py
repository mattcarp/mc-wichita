"""Marine distress decoders (DSC Ch70 + COSPAS-SARSAT 406) and dashboard alerting."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from scipy.signal import resample

import alert_store
from dsc_decoder.audio.loader import load_audio
from dsc_decoder.demodulation.band_detector import DSCBandDetector
from dsc_decoder.demodulation.fsk_demod import FSKDemodulator
from dsc_decoder.decoding.message_parser import MessageParser, find_all_phasings, PHASING_LEN
from dsc_decoder.decoding.symbol_decoder import SymbolDecoder
from wichita_iq import IqCapture, load_iq_file, nfm_audio_from_iq
from wichita_live_events import append_event
from wichita_sarsat406 import decode_from_audio_wav, decode_from_fm_audio

logger = logging.getLogger(__name__)

DSC_CH70_HZ = 156_525_000.0
EPIRB_CENTER_HZ = 406_028_000.0

DISTRESS_FORMAT_CODES = {112, 114, 116}  # distress, distress ack, distress relay
URGENCY_CATEGORY = 110
SAFETY_CATEGORY = 108
DISTRESS_CATEGORY = 112


def _decode_dsc_from_audio(samples: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
    detector = DSCBandDetector()
    params = detector.detect_band(samples, sample_rate)
    demod = FSKDemodulator(
        method="goertzel",
        baud_rate=params["baud_rate"],
        f_space=params["f_space"],
        f_mark=params["f_mark"],
    )
    bitstream = demod.demodulate(samples, sample_rate)
    symbol_decoder = SymbolDecoder()
    bits_list = bitstream.tolist()
    candidates: List[Any] = []
    for offset in range(10):
        stream = symbol_decoder.decode_stream(bits_list, start_offset=offset)
        syms_only = [s for s, _ in stream]
        for ph_idx in find_all_phasings(syms_only):
            window = stream[ph_idx : ph_idx + PHASING_LEN + 100]
            if len(window) >= 25:
                candidates.append(window)
    parser = MessageParser()
    messages = parser.parse_multiple(candidates)
    out: List[Dict[str, Any]] = []
    for msg in messages:
        if msg is None:
            continue
        d = msg.to_dict() if hasattr(msg, "to_dict") else dict(msg)
        if d.get("is_valid"):
            out.append(d)
    return out


def decode_dsc_file(path: Union[str, Path]) -> List[Dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() in {".wav", ".wave"}:
        samples, sr = load_audio(str(p))
        return _decode_dsc_from_audio(samples, sr)
    cap = load_iq_file(p, sample_rate_hz=float(os.environ.get("WICHITA_IQ_SAMPLE_RATE", "2000000")))
    audio, ar = nfm_audio_from_iq(cap, audio_rate=48_000, deviation_hz=5_000.0)
    target_sr = 22_050
    if ar != target_sr:
        audio = resample(audio, int(len(audio) * target_sr / ar)).astype(np.float32)
        ar = target_sr
    return _decode_dsc_from_audio(audio, ar)


def decode_epirb_file(path: Union[str, Path]) -> List[Dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() in {".wav", ".wave"}:
        frames = decode_from_audio_wav(p)
    else:
        cap = load_iq_file(p, sample_rate_hz=float(os.environ.get("WICHITA_IQ_SAMPLE_RATE", "2000000")))
        audio, ar = nfm_audio_from_iq(cap, audio_rate=48_000, deviation_hz=5_000.0)
        frames = decode_from_fm_audio(audio, ar)
    return [f.to_dict() for f in frames]


def _dsc_priority(parsed: Dict[str, Any]) -> str:
    cat = parsed.get("category") or ""
    fmt_code = parsed.get("format_code")
    if fmt_code is not None:
        try:
            fmt_code = int(fmt_code)
        except (TypeError, ValueError):
            fmt_code = None
    if (
        fmt_code in DISTRESS_FORMAT_CODES
        or cat == "Distress"
        or parsed.get("distress_mmsi")
        or parsed.get("tc1") in ("Distress acknowledgement", "Distress alert")
        or parsed.get("tc1_code") in (110, 112)
    ):
        return "distress"
    if cat == "Urgency":
        return "urgency"
    if cat == "Safety":
        return "safety"
    return "routine"


def _dsc_sentence(parsed: Dict[str, Any]) -> str:
    pri = _dsc_priority(parsed)
    fmt = parsed.get("format") or "DSC"
    self_mmsi = parsed.get("self_id_mmsi") or parsed.get("address_mmsi") or "unknown"
    parts = [f"{pri.upper()}: {fmt}", f"MMSI {self_mmsi}"]
    if parsed.get("distress_nature"):
        parts.append(str(parsed["distress_nature"]))
    pos = parsed.get("position")
    if pos and isinstance(pos, dict):
        parts.append(f"{pos.get('lat_str', '')} {pos.get('lon_str', '')}".strip())
    if parsed.get("time_utc"):
        parts.append(f"UTC {parsed['time_utc']}")
    return " · ".join(p for p in parts if p)


def _lookup_ais_mmsi(mmsi: Optional[str]) -> Optional[Dict[str, Any]]:
    if not mmsi or not str(mmsi).isdigit():
        return None
    try:
        import wichita_ais_live as wal

        detail, err = wal.live_ship_detail(int(mmsi))
        if detail and not err:
            return detail
    except Exception as exc:
        logger.debug("AIS link lookup failed for %s: %s", mmsi, exc)
    return None


def _emit_timeline_and_alert(
    *,
    kind: str,
    sentence: str,
    title: str,
    frequency_mhz: float,
    signal_type: str,
    metadata: Dict[str, Any],
    mmsi: Optional[str] = None,
) -> Dict[str, Any]:
    ev = append_event(kind, sentence, mmsi=int(mmsi) if mmsi and mmsi.isdigit() else None, **metadata)
    alert_id = str(uuid.uuid4())
    record = {
        "id": alert_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "description": sentence,
        "signal_type": signal_type,
        "severity": "critical" if kind.endswith("_distress") else "warning",
        "frequency_mhz": frequency_mhz,
        "confidence": metadata.get("confidence", 1.0),
        "transcript": None,
        "language": None,
        "audio_url": None,
        "tags": ["marine", "distress", metadata.get("decoder", "unknown")],
        "metadata": metadata,
        "source": "wichita_distress",
        "review_status": "pending_review",
    }
    alert_store.append_alert_record(record)
    return {"event": ev, "alert_id": alert_id}


def ingest_dsc_messages(messages: List[Dict[str, Any]], *, source: str = "live") -> List[Dict[str, Any]]:
    raised: List[Dict[str, Any]] = []
    for parsed in messages:
        pri = _dsc_priority(parsed)
        self_mmsi = parsed.get("self_id_mmsi") or parsed.get("address_mmsi")
        ais = _lookup_ais_mmsi(str(self_mmsi) if self_mmsi else None)
        meta = {
            "decoder": "dsc",
            "source": source,
            "priority": pri,
            "dsc": parsed,
            "ais_vessel": ais,
            "confidence": parsed.get("confidence", 1.0),
        }
        sentence = _dsc_sentence(parsed)
        if pri == "distress":
            kind = "marine_distress_dsc"
            title = "DSC distress alert (Ch 70)"
        elif pri == "urgency":
            kind = "marine_urgency_dsc"
            title = "DSC urgency call (Ch 70)"
        elif pri == "safety":
            kind = "marine_safety_dsc"
            title = "DSC safety call (Ch 70)"
        else:
            continue  # routine DSC not surfaced as top-priority alerts
        raised.append(
            _emit_timeline_and_alert(
                kind=kind,
                sentence=sentence,
                title=title,
                frequency_mhz=DSC_CH70_HZ / 1e6,
                signal_type="distress" if pri == "distress" else "marine_dsc",
                metadata=meta,
                mmsi=str(self_mmsi) if self_mmsi else None,
            )
        )
    return raised


def ingest_epirb_frames(frames: List[Dict[str, Any]], *, source: str = "live") -> List[Dict[str, Any]]:
    raised: List[Dict[str, Any]] = []
    for raw in frames:
        pri = "distress" if not raw.get("is_test") else "test"
        if raw.get("is_test"):
            continue  # self-test beacons: decode path verified in tests, not operator alerts
        hex_id = raw.get("hex_id") or "unknown"
        pos = ""
        if raw.get("latitude") is not None and raw.get("longitude") is not None:
            pos = f" at {raw['latitude']:.4f}, {raw['longitude']:.4f}"
        sentence = f"406 MHz {raw.get('beacon_type', 'beacon')}: {hex_id}{pos}"
        meta = {"decoder": "sarsat406", "source": source, "frame": raw}
        raised.append(
            _emit_timeline_and_alert(
                kind="marine_distress_406",
                sentence=sentence,
                title="COSPAS-SARSAT 406 MHz beacon",
                frequency_mhz=EPIRB_CENTER_HZ / 1e6,
                signal_type="distress",
                metadata=meta,
            )
        )
    return raised


def replay_capture(path: Union[str, Path]) -> Dict[str, Any]:
    """Decode a stored WAV or IQ capture; returns decoded messages without raising live alerts."""
    p = Path(path)
    name = p.name.lower()
    if "406" in name or "epirb" in name or "sarsat" in name:
        frames = decode_epirb_file(p)
        return {"kind": "epirb", "messages": frames}
    dsc = decode_dsc_file(p)
    return {"kind": "dsc", "messages": dsc}

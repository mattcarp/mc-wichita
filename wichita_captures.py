"""
Read-only scanner for Wichita capture folders on disk.
Folder layout: <root>/<UTC timestamp>[_suffix]/
"""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

MALTA_TZ = ZoneInfo("Europe/Malta")

CAPTURE_DIR_RE = re.compile(
    r"^(?P<date>\d{8})T(?P<time>\d{6})Z(?P<suffix>.*)$"
)

VALLETTA_AIS_BASE_MMSIS = {2155001, 21550001}
KNOWN_SPUR_MHZ = (120.0, 132.0)
MARINE_BOOKMARKS_MHZ = {
    "CH09": 156.450,
    "CH16": 156.800,
    "CH70": 156.525,
    "AIS1": 161.975,
    "AIS2": 162.025,
}
MARINE_PSD_MIN_MHZ = 156.45
MARINE_PSD_MAX_MHZ = 162.4
PSD_EDGE_MARGIN_BINS = 4
AIRBAND_WATCH_MHZ = {
    "121.5_distress": 121.5,
    "123.1_SAR": 123.1,
}


def captures_roots_from_env() -> List[Path]:
    raw = os.environ.get("WICHITA_CAPTURES_DIRS", "")
    roots = [Path(p).expanduser().resolve() for p in raw.split(":") if p.strip()]
    return [r for r in roots if r.is_dir()]


def parse_capture_folder_name(name: str) -> Optional[datetime]:
    m = CAPTURE_DIR_RE.match(name)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group("date") + m.group("time"), "%Y%m%d%H%M%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def folder_suffix(name: str) -> str:
    m = CAPTURE_DIR_RE.match(name)
    if not m:
        return ""
    return (m.group("suffix") or "").lstrip("_")


@dataclass(frozen=True)
class CaptureRef:
    capture_id: str
    path: Path
    start_utc: datetime
    suffix: str

    @property
    def sort_key(self) -> datetime:
        return self.start_utc


def scan_captures(roots: Optional[Iterable[Path]] = None) -> List[CaptureRef]:
    if roots is None:
        roots = captures_roots_from_env()
    found: Dict[str, CaptureRef] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            start = parse_capture_folder_name(child.name)
            if start is None:
                continue
            ref = CaptureRef(
                capture_id=child.name,
                path=child,
                start_utc=start,
                suffix=folder_suffix(child.name),
            )
            prev = found.get(ref.capture_id)
            if prev is None or ref.path.stat().st_mtime > prev.path.stat().st_mtime:
                found[ref.capture_id] = ref
    return sorted(found.values(), key=lambda r: r.sort_key, reverse=True)


def _malta_hm(ts: float) -> str:
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .astimezone(MALTA_TZ)
        .strftime("%H:%M")
    )


def _malta_time_range(t0: float, t1: float) -> str:
    return f"{_malta_hm(t0)}–{_malta_hm(t1)} Malta"


def _load_capture_settings(capture_dir: Path) -> Dict[str, Any]:
    direct = capture_dir / "capture_settings.json"
    if direct.is_file():
        data = _read_json(direct)
        return data or {}
    candidates = sorted(capture_dir.glob("*capture_settings.json"))
    for path in candidates:
        if "wichita_vhf" in path.name or "marine" in path.name:
            data = _read_json(path)
            if data:
                return data
    if candidates:
        data = _read_json(candidates[0])
        return data or {}
    return {}


def _load_primary_sigmf_meta(capture_dir: Path) -> Dict[str, Any]:
    direct = list(capture_dir.glob("*.sigmf-meta"))
    if not direct:
        return {}
    preferred = [p for p in direct if "wichita_vhf" in p.name or "marine" in p.name]
    path = preferred[0] if preferred else sorted(direct)[0]
    data = _read_json(path)
    if not data:
        return {}
    return data.get("global") or data


def _device_serial_from_stdout(capture_dir: Path) -> Optional[str]:
    for path in sorted(capture_dir.glob("*capture_stdout.log")):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "SerNo:" in line:
                    return line.split("SerNo:", 1)[1].strip()
        except OSError:
            continue
    return None


def station_snapshot_from_capture(ref: CaptureRef) -> Dict[str, Any]:
    settings = _load_capture_settings(ref.path)
    sigmf = _load_primary_sigmf_meta(ref.path)
    manifest = load_manifest(ref.path)
    readback = None
    rb = settings.get("readback")
    if isinstance(rb, list) and rb:
        readback = rb[-1]
    elif isinstance(rb, dict):
        readback = rb
    bias_meta = sigmf.get("wichita:biasT_readback") or {}
    bias_t = None
    if readback and readback.get("biasT_ctrl") is not None:
        bias_t = readback.get("biasT_ctrl")
    elif bias_meta:
        bias_t = bias_meta.get("during_stream") or bias_meta.get("pre_stream")
    serial = sigmf.get("wichita:device_serial") or _device_serial_from_stdout(ref.path)
    tuner_hz = None
    if readback and readback.get("frequency"):
        tuner_hz = float(readback["frequency"])
    hw = sigmf.get("core:hw") or "SDRplay RSPdx-R2 (receive-only)"
    overflows = settings.get("overflows")
    if overflows is None:
        overflows = 0
    return {
        "source_capture_id": ref.capture_id,
        "source_label": f"from capture {ref.capture_id}",
        "receiver": hw,
        "device_serial": serial or "not recorded",
        "bias_t": str(bias_t).lower() if bias_t is not None else "not recorded",
        "overflows": overflows,
        "noise_rms_dbfs": settings.get("rms_dbfs"),
        "peak_dbfs": settings.get("peak_dbfs"),
        "tuner_center_mhz": (tuner_hz / 1e6) if tuner_hz else None,
        "antenna_note": manifest.get("location") or sigmf.get("wichita:location"),
        "known_spurs_mhz": [
            {"mhz": 120.0, "label": "known local spur"},
            {"mhz": 132.0, "label": "known local spur"},
        ],
    }


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_manifest(capture_dir: Path) -> Dict[str, Any]:
    data = _read_json(capture_dir / "manifest.json")
    return data or {}


def folder_sha256(manifest: Dict[str, Any]) -> Optional[str]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    # Prefer a stable aggregate if present
    if manifest.get("folder_sha256"):
        return str(manifest["folder_sha256"])
    keys = sorted(files.keys())
    if not keys:
        return None
    first = files[keys[0]]
    if isinstance(first, dict) and first.get("sha256"):
        return f"{len(keys)} files · first {first['sha256'][:16]}…"
    return None


def list_audio_files(capture_dir: Path, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    files_meta = manifest.get("files") or {}
    out: List[Dict[str, Any]] = []
    if not isinstance(files_meta, dict):
        return out
    for name, meta in sorted(files_meta.items()):
        if not name.lower().endswith(".wav"):
            continue
        p = capture_dir / name
        entry = {
            "filename": name,
            "present": p.is_file(),
            "bytes": meta.get("bytes") if isinstance(meta, dict) else None,
            "sha256": meta.get("sha256") if isinstance(meta, dict) else None,
        }
        out.append(entry)
    return out


def mmsi_label(mmsi: int) -> str:
    if mmsi in VALLETTA_AIS_BASE_MMSIS or f"{mmsi:09d}" == "002155001":
        return "Valletta AIS base station"
    return f"MMSI {mmsi:09d}"


def normalize_mmsi(raw: Any) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def decode_ais_from_nmea(capture_dir: Path, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    if analysis.get("ais_messages"):
        for row in analysis["ais_messages"]:
            mmsi = normalize_mmsi(row.get("mmsi"))
            messages.append(
                {
                    "t_s": row.get("t_s"),
                    "channel": row.get("channel"),
                    "type": row.get("type"),
                    "mmsi": mmsi,
                    "mmsi_display": f"{mmsi:09d}",
                    "label": mmsi_label(mmsi) if mmsi else None,
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "nmea": row.get("nmea"),
                    "source": "analysis_report.json",
                }
            )
        return messages

    nmea_path = capture_dir / "ais_decoded.nmea"
    if not nmea_path.is_file():
        return messages

    lines = [
        ln.strip()
        for ln in nmea_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    try:
        from ais_decoder import decode_nmea_lines

        decoded = decode_nmea_lines(lines)
        for v in decoded:
            mmsi = normalize_mmsi(v.get("mmsi"))
            messages.append(
                {
                    "mmsi": mmsi,
                    "mmsi_display": f"{mmsi:09d}",
                    "label": mmsi_label(mmsi),
                    "lat": v.get("lat"),
                    "lon": v.get("lon"),
                    "name": v.get("name"),
                    "msg_type": v.get("msg_type"),
                    "source": "ais_decoded.nmea",
                }
            )
    except Exception:
        for i, ln in enumerate(lines):
            messages.append({"line": ln, "index": i, "source": "ais_decoded.nmea"})
    return messages


def load_wideband_psd(capture_dir: Path, max_points: int = 2048) -> Dict[str, Any]:
    path = capture_dir / "wideband_psd.csv"
    if not path.is_file():
        return {"available": False, "reason": "wideband_psd.csv not found"}
    freqs: List[float] = []
    psd: List[float] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if row[0].strip() in {"freq_hz", "frequency_hz"}:
                continue
            try:
                freqs.append(float(row[0]) / 1e6)
                psd.append(float(row[1]))
            except (ValueError, IndexError):
                continue
    if not freqs:
        return {"available": False, "reason": "wideband_psd.csv empty"}
    trimmed_low_mhz: Optional[float] = None
    if freqs:
        while freqs and freqs[0] < MARINE_PSD_MIN_MHZ:
            trimmed_low_mhz = freqs[0] / 1e6 if freqs[0] > 1e5 else freqs[0]
            freqs.pop(0)
            psd.pop(0)
        while freqs and freqs[-1] > MARINE_PSD_MAX_MHZ:
            freqs.pop()
            psd.pop()
    trimmed_high_mhz: Optional[float] = None
    if freqs and freqs[-1] < MARINE_PSD_MAX_MHZ - 0.01:
        trimmed_high_mhz = MARINE_PSD_MAX_MHZ
    if len(freqs) > PSD_EDGE_MARGIN_BINS * 2 + 8:
        freqs = freqs[PSD_EDGE_MARGIN_BINS:-PSD_EDGE_MARGIN_BINS]
        psd = psd[PSD_EDGE_MARGIN_BINS:-PSD_EDGE_MARGIN_BINS]
    if len(freqs) > max_points:
        step = max(1, len(freqs) // max_points)
        freqs = freqs[::step][:max_points]
        psd = psd[::step][:max_points]
    analysis = _read_json(capture_dir / "analysis_report.json") or {}
    settings = _load_capture_settings(capture_dir)
    sigmf = _load_primary_sigmf_meta(capture_dir)
    rb = settings.get("readback")
    if isinstance(rb, list) and rb:
        rb = rb[-1]
    tuner_mhz = None
    if isinstance(rb, dict) and rb.get("frequency"):
        tuner_mhz = float(rb["frequency"]) / 1e6
    trim_parts = []
    if trimmed_low_mhz is not None:
        trim_parts.append(f"Left roll-off trimmed below {MARINE_PSD_MIN_MHZ:.3f} MHz")
    if trimmed_high_mhz is not None:
        trim_parts.append(f"Right roll-off trimmed above {MARINE_PSD_MAX_MHZ:.3f} MHz")
    return {
        "available": True,
        "freq_mhz": freqs,
        "psd_db_per_hz": psd,
        "bookmarks_mhz": MARINE_BOOKMARKS_MHZ,
        "median_db": analysis.get("wideband_psd_median_db"),
        "display_kind": "averaged_psd",
        "trimmed_low_mhz": trimmed_low_mhz,
        "trimmed_high_mhz": trimmed_high_mhz,
        "tuner_center_mhz": tuner_mhz,
        "trim_note": "; ".join(trim_parts) if trim_parts else None,
    }


def marine_watch_payload(capture_dir: Path, analysis: Dict[str, Any]) -> Dict[str, Any]:
    channels = (analysis.get("channels") or {}) if analysis else {}
    ch16 = channels.get("CH16_156.800") or {}
    ch09 = channels.get("CH09_156.450") or {}
    coincidence = analysis.get("ch16_ch09_coincidence") or {}
    interference_note = None
    if coincidence.get("ch16_overlapping_ch09") or coincidence.get("ch09_overlapping_ch16"):
        interference_note = (
            "Both marine channels showed activity at once — may be local interference, not two real transmitters."
        )

    def channel_tile(key: str, data: Dict[str, Any], label: str) -> Dict[str, Any]:
        openings = data.get("squelch_openings_ge_0.3s") or []
        return {
            "label": label,
            "noise_floor_dbfs": data.get("noise_floor_dbfs_5ms_p20"),
            "peak_over_noise_db": data.get("peak_over_noise_db"),
            "squelch_openings": openings,
            "quiet": len(openings) == 0,
            "wav": Path(data.get("wav") or "").name if data.get("wav") else None,
        }

    return {
        "ch16": channel_tile("ch16", ch16, "Channel 16"),
        "ch09": channel_tile("ch09", ch09, "Channel 09"),
        "interference_note": interference_note,
        "coincidence": coincidence,
    }


def airband_payload(capture_dir: Path) -> Dict[str, Any]:
    scan = _read_json(capture_dir / "airband_scan_118_137.json")
    voice_reports: List[Dict[str, Any]] = []
    for path in capture_dir.glob("*voice_report.json"):
        rep = _read_json(path)
        if rep:
            voice_reports.append({"file": path.name, "report": rep})

    if not scan and not voice_reports:
        return {"available": False, "reason": "No airband scan or voice reports in this capture"}

    channels = []
    if scan:
        floor = scan.get("floor_db")
        for ch in scan.get("channels") or []:
            freq = ch.get("freq_mhz")
            tag = None
            if freq is not None:
                if abs(freq - 121.5) < 0.02:
                    tag = "121.5 distress guard"
                elif abs(freq - 123.1) < 0.02:
                    tag = "123.1 SAR"
                elif abs(freq - 120.0) < 0.02:
                    tag = "known local spur"
                elif abs(freq - 132.0) < 0.02:
                    tag = "known local spur"
            channels.append(
                {
                    "freq_mhz": freq,
                    "maxhold_over_floor_db": ch.get("maxhold_over_floor_db"),
                    "avg_over_floor_db": ch.get("avg_over_floor_db"),
                    "tag": tag,
                }
            )
    watch: Dict[str, Any] = {}
    for rep_wrap in voice_reports:
        rep = rep_wrap.get("report") or {}
        for ch_key, ch_data in (rep.get("channels") or {}).items():
            freq_hz = ch_data.get("freq_hz") or 0
            freq_mhz = freq_hz / 1e6 if freq_hz else None
            openings = ch_data.get("openings_ge_0p3s_8db") or ch_data.get(
                "openings_ge_0.3s_8db"
            ) or []
            watch[ch_key] = {
                "freq_mhz": freq_mhz,
                "quiet": len(openings) == 0,
                "openings": openings,
                "peak_over_noise_db": ch_data.get("peak_over_noise_db"),
            }

    return {
        "available": True,
        "readback": (scan or {}).get("readback"),
        "dwell_s": (scan or {}).get("dwell_s"),
        "channels": channels,
        "watch": watch,
        "known_spurs_mhz": list(KNOWN_SPUR_MHZ),
    }


def _is_known_base_station(mmsi: int) -> bool:
    return mmsi in VALLETTA_AIS_BASE_MMSIS


def _append_ais_timeline_events(
    events: List[Dict[str, Any]],
    capture_ref: CaptureRef,
    ais_messages: List[Dict[str, Any]],
) -> None:
    start = capture_ref.start_utc
    by_mmsi: Dict[int, List[Dict[str, Any]]] = {}
    for msg in ais_messages:
        mmsi = normalize_mmsi(msg.get("mmsi"))
        if mmsi:
            by_mmsi.setdefault(mmsi, []).append(msg)

    for mmsi, msgs in by_mmsi.items():
        timed = [m for m in msgs if m.get("t_s") is not None]
        label = msgs[0].get("label") or mmsi_label(mmsi)
        if _is_known_base_station(mmsi) and timed:
            times = sorted(float(m["t_s"]) for m in timed)
            t0 = start.timestamp() + times[0]
            t1 = start.timestamp() + times[-1]
            events.append(
                {
                    "kind": "ais_summary",
                    "t_utc": t0,
                    "title": f"{label} heard {len(timed)} times",
                    "detail": (
                        f"Routine AIS in this capture · {_malta_time_range(t0, t1)}"
                    ),
                    "caution": None,
                    "grouped": True,
                    "meta": {"mmsi": mmsi, "count": len(timed), "label": label},
                }
            )
            continue

        # Vessels or unknown carriers: one summary per MMSI unless only a single message
        if len(timed) > 3:
            times = sorted(float(m["t_s"]) for m in timed)
            t0 = start.timestamp() + times[0]
            t1 = start.timestamp() + times[-1]
            events.append(
                {
                    "kind": "ais_vessel_summary",
                    "t_utc": t0,
                    "title": f"{label} — {len(timed)} messages",
                    "detail": "Vessel or mobile station in range (not the Valletta base).",
                    "caution": None,
                    "grouped": True,
                    "meta": {"mmsi": mmsi, "count": len(timed)},
                }
            )
        else:
            for msg in timed:
                t_s = float(msg["t_s"])
                events.append(
                    {
                        "kind": "ais",
                        "t_utc": start.timestamp() + t_s,
                        "title": "AIS from vessel or unknown station",
                        "detail": label,
                        "caution": "New or infrequent AIS — worth a glance, not an alert.",
                        "grouped": False,
                        "meta": msg,
                    }
                )


def build_timeline(
    capture_ref: CaptureRef,
    analysis: Dict[str, Any],
    ais_messages: List[Dict[str, Any]],
    marine: Dict[str, Any],
    airband: Dict[str, Any],
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    start = capture_ref.start_utc

    _append_ais_timeline_events(events, capture_ref, ais_messages)

    for ch_key, tile in (("ch16", marine.get("ch16")), ("ch09", marine.get("ch09"))):
        if not tile:
            continue
        for op in tile.get("squelch_openings") or []:
            t_s = op.get("t_s") or op.get("start_s")
            events.append(
                {
                    "kind": "squelch",
                    "t_utc": (start.timestamp() + float(t_s)) if t_s is not None else None,
                    "title": f"{tile.get('label')} squelch open",
                    "detail": f"Duration {op.get('dur_ms', '?')} ms",
                    "caution": "Possible voice activity — not confirmed as distress.",
                    "meta": {"channel": ch_key, **op},
                }
            )

    settings = _read_json(capture_ref.path / "capture_settings.json") or {}
    if settings.get("overflows"):
        events.append(
            {
                "kind": "system",
                "t_utc": start.timestamp(),
                "title": "SDR buffer overflow",
                "detail": f"{settings.get('overflows')} overflow(s) during capture",
                "caution": None,
                "meta": {"overflows": settings.get("overflows")},
            }
        )

    if airband.get("available"):
        for ch_key, tile in (airband.get("watch") or {}).items():
            for op in tile.get("openings") or []:
                t_s = op.get("t_s") or op.get("start_s")
                events.append(
                    {
                        "kind": "airband",
                        "t_utc": (start.timestamp() + float(t_s)) if t_s is not None else None,
                        "title": f"Airband activity ({ch_key})",
                        "detail": "Possible transmission — not confirmed.",
                        "caution": "Possible call for help, not confirmed.",
                        "meta": {"channel": ch_key, **op},
                    }
                )

    events.sort(key=lambda e: e.get("t_utc") or 0)
    for e in events:
        if e.get("t_utc") is not None:
            e["time_utc"] = datetime.fromtimestamp(
                e["t_utc"], tz=timezone.utc
            ).isoformat()
    return events


def capture_picker_label(ref: CaptureRef) -> str:
    manifest = load_manifest(ref.path)
    loc = (manifest.get("location") or "").lower()
    if "balcony" in loc or "stairwell" in loc:
        place = "Balcony"
    elif "indoor" in loc:
        place = "Indoor"
    elif ref.suffix == "voice" or "voice" in ref.capture_id:
        place = "Voice test"
    else:
        place = "Capture"
    local = ref.start_utc.astimezone(MALTA_TZ)
    when = f"{local.day} {local.strftime('%b %H:%M')}"
    return f"{place} · {when}"


def capture_summary(ref: CaptureRef) -> Dict[str, Any]:
    manifest = load_manifest(ref.path)
    analysis = _read_json(ref.path / "analysis_report.json") or {}
    ais = decode_ais_from_nmea(ref.path, analysis)
    marine = marine_watch_payload(ref.path, analysis)
    airband = airband_payload(ref.path)
    unique_mmsi = sorted(
        {normalize_mmsi(m.get("mmsi")) for m in ais if m.get("mmsi")}
    )
    vessels = [m for m in unique_mmsi if m not in VALLETTA_AIS_BASE_MMSIS]
    return {
        "capture_id": ref.capture_id,
        "start_utc": ref.start_utc.isoformat(),
        "suffix": ref.suffix,
        "location": manifest.get("location"),
        "capture_context": manifest.get("capture_context"),
        "provenance_status": manifest.get("provenance_status", "unknown"),
        "provenance_basis": manifest.get("provenance_basis"),
        "folder_sha256": folder_sha256(manifest),
        "has_wideband_psd": (ref.path / "wideband_psd.csv").is_file(),
        "has_analysis": bool(analysis),
        "ais_message_count": len(ais),
        "ais_unique_mmsi": unique_mmsi,
        "vessel_count": len(vessels),
        "base_station_count": len(unique_mmsi) - len(vessels),
        "audio_files": list_audio_files(ref.path, manifest),
        "marine_quiet": marine.get("ch16", {}).get("quiet")
        and marine.get("ch09", {}).get("quiet"),
        "wideband_psd_median_db": analysis.get("wideband_psd_median_db"),
        "overflows": _load_capture_settings(ref.path).get("overflows"),
        "picker_label": capture_picker_label(ref),
    }


def capture_detail(ref: CaptureRef) -> Dict[str, Any]:
    manifest = load_manifest(ref.path)
    analysis = _read_json(ref.path / "analysis_report.json") or {}
    ais = decode_ais_from_nmea(ref.path, analysis)
    marine = marine_watch_payload(ref.path, analysis)
    airband = airband_payload(ref.path)
    settings = _load_capture_settings(ref.path)
    timeline = build_timeline(ref, analysis, ais, marine, airband)
    return {
        "summary": capture_summary(ref),
        "manifest": manifest,
        "analysis": analysis,
        "ais": ais,
        "marine_watch": marine,
        "airband": airband,
        "capture_settings": settings,
        "timeline": timeline,
        "station_snapshot": station_snapshot_from_capture(ref),
    }


def dashboard_aggregate(refs: List[CaptureRef]) -> Dict[str, Any]:
    if not refs:
        return {
            "available": False,
            "message": "No capture folders found. Set WICHITA_CAPTURES_DIRS to your capture library.",
            "captures": [],
        }
    primary = refs[0]
    detail = capture_detail(primary)
    psd = load_wideband_psd(primary.path)
    if psd.get("available") and detail.get("analysis"):
        psd["median_db"] = detail["analysis"].get("wideband_psd_median_db")
    comparison = []
    for ref in refs[:3]:
        comparison.append(capture_summary(ref))
    return {
        "available": True,
        "primary_capture_id": primary.capture_id,
        "timezone": "Europe/Malta",
        "primary": detail,
        "psd": psd,
        "recent_captures": comparison,
        "station": station_payload(refs),
    }


def station_payload(refs: List[CaptureRef]) -> Dict[str, Any]:
    primary = refs[0] if refs else None
    if not primary:
        return {"capture_comparison": []}
    snap = station_snapshot_from_capture(primary)
    snap["capture_comparison"] = [
        {
            "capture_id": r.capture_id,
            "picker_label": capture_picker_label(r),
            "ais_message_count": capture_summary(r).get("ais_message_count"),
        }
        for r in refs[:5]
    ]
    return snap


def resolve_capture(capture_id: str, roots: Optional[Iterable[Path]] = None) -> Optional[CaptureRef]:
    for ref in scan_captures(roots):
        if ref.capture_id == capture_id:
            return ref
    return None

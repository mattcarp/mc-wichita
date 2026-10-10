"""24-48 h ADS-B position ring buffer for emergency-squawk replay."""

from __future__ import annotations

import json
import os
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from wichita_adsb_live import EMERGENCY_SQUAWKS

OBSERVED_CAVEAT = (
    "Observed data from our antenna only — not ground truth, not official ATC, "
    "and may be incomplete or wrong."
)

_TRACK_HOURS = float(os.environ.get("WICHITA_ADSB_TRACK_HOURS", "48"))
_MAX_POINTS_PER_HEX = int(os.environ.get("WICHITA_ADSB_TRACK_MAX_POINTS", "8000"))


def tracks_dir() -> Path:
    raw = os.environ.get("WICHITA_ADSB_TRACKS_DIR", "~/wichita/live/adsb_tracks").strip()
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _track_path(hex_id: str) -> Path:
    safe = hex_id.lower().replace("/", "_")
    return tracks_dir() / f"{safe}.jsonl"


class AdsbTrackStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recent: Deque[Dict[str, Any]] = deque(maxlen=50000)

    def record_snapshot(self, planes: List[Dict[str, Any]], server_time_utc: str) -> None:
        if not planes:
            return
        try:
            ts = datetime.fromisoformat(server_time_utc.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            ts = datetime.now(timezone.utc)
        cutoff = ts - timedelta(hours=_TRACK_HOURS)
        with self._lock:
            for p in planes:
                hex_id = (p.get("hex") or p.get("id") or "").lower()
                if not hex_id:
                    continue
                rec = {
                    "ts_utc": ts.isoformat(),
                    "hex": hex_id,
                    "lat": p.get("lat"),
                    "lon": p.get("lon"),
                    "altitude_ft": p.get("altitude_ft"),
                    "speed_kts": p.get("speed_kts"),
                    "heading_deg": p.get("heading_deg"),
                    "squawk": p.get("squawk"),
                    "callsign": p.get("callsign"),
                }
                self._recent.append(rec)
                self._append_disk(hex_id, rec, cutoff)

    def _append_disk(self, hex_id: str, rec: Dict[str, Any], cutoff: datetime) -> None:
        path = _track_path(hex_id)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._trim_file(path, cutoff)

    def _trim_file(self, path: Path, cutoff: datetime) -> None:
        if not path.is_file():
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        kept: List[str] = []
        for line in lines[-_MAX_POINTS_PER_HEX:]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                ts = datetime.fromisoformat(row["ts_utc"].replace("Z", "+00:00"))
            except (KeyError, ValueError, json.JSONDecodeError):
                continue
            if ts >= cutoff:
                kept.append(line)
        if len(kept) < len(lines):
            path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    def track_for_hex(self, hex_id: str, hours: Optional[float] = None) -> List[Dict[str, Any]]:
        hours = hours or _TRACK_HOURS
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        path = _track_path(hex_id.lower())
        out: List[Dict[str, Any]] = []
        if path.is_file():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    ts = datetime.fromisoformat(row["ts_utc"].replace("Z", "+00:00"))
                    if ts >= cutoff:
                        out.append(row)
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                pass
        out.sort(key=lambda r: r.get("ts_utc", ""))
        return out

    def emergency_replays(self, hours: Optional[float] = None) -> List[Dict[str, Any]]:
        hours = hours or _TRACK_HOURS
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        root = tracks_dir()
        replays: List[Dict[str, Any]] = []
        for path in root.glob("*.jsonl"):
            hex_id = path.stem
            track = self.track_for_hex(hex_id, hours=hours)
            squawks = {str(r.get("squawk")).strip() for r in track if r.get("squawk")}
            hit = [s for s in squawks if s in EMERGENCY_SQUAWKS]
            if not hit:
                continue
            first = track[0]["ts_utc"] if track else None
            last = track[-1]["ts_utc"] if track else None
            replays.append(
                {
                    "hex": hex_id,
                    "squawks": hit,
                    "squawk_notes": [EMERGENCY_SQUAWKS[s] for s in hit],
                    "point_count": len(track),
                    "first_ts_utc": first,
                    "last_ts_utc": last,
                    "caveat": OBSERVED_CAVEAT,
                }
            )
        replays.sort(key=lambda r: r.get("last_ts_utc") or "", reverse=True)
        return replays


_store: Optional[AdsbTrackStore] = None


def get_track_store() -> AdsbTrackStore:
    global _store
    if _store is None:
        _store = AdsbTrackStore()
    return _store

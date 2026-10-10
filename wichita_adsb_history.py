"""24–48 h ring buffer of ADS-B positions (disk JSONL, read-only ingest)."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

EMERGENCY_SQUAWKS = frozenset({"7500", "7600", "7700"})
DEFAULT_RETENTION_H = float(os.environ.get("WICHITA_ADSB_HISTORY_HOURS", "48"))


def history_dir() -> Path:
    raw = os.environ.get("WICHITA_ADSB_HISTORY_DIR", "~/wichita/live/adsb-history").strip()
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _day_path(when: datetime) -> Path:
    return history_dir() / f"adsb-{when.strftime('%Y-%m-%d')}.jsonl"


class AdsbHistoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def record_snapshot(self, aircraft: List[Dict[str, Any]], server_now: Optional[float] = None) -> None:
        if not aircraft:
            return
        now = datetime.now(timezone.utc)
        path = _day_path(now)
        with self._lock, path.open("a", encoding="utf-8") as fh:
            for ac in aircraft:
                rec = {
                    "ts_utc": now.isoformat(),
                    "server_now": server_now,
                    "hex": ac.get("hex"),
                    "lat": ac.get("lat"),
                    "lon": ac.get("lon"),
                    "altitude_ft": ac.get("altitude_ft"),
                    "speed_kts": ac.get("speed_kts"),
                    "heading_deg": ac.get("heading_deg"),
                    "squawk": ac.get("squawk"),
                    "callsign": ac.get("callsign"),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _read_window(self, hours: float) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        out: List[Dict[str, Any]] = []
        root = history_dir()
        if not root.is_dir():
            return out
        for path in sorted(root.glob("adsb-*.jsonl")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = rec.get("ts_utc")
                if not ts:
                    continue
                try:
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if when < cutoff:
                    continue
                out.append(rec)
        out.sort(key=lambda r: r.get("ts_utc") or "")
        return out

    def positions_since(self, hours: float = 24.0, hex_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self._read_window(min(hours, DEFAULT_RETENTION_H))
        if hex_id:
            hid = hex_id.strip().lower()
            rows = [r for r in rows if (r.get("hex") or "").lower() == hid]
        return rows

    def emergency_replay(self, hours: float = 48.0) -> List[Dict[str, Any]]:
        rows = self._read_window(min(hours, DEFAULT_RETENTION_H))
        events: List[Dict[str, Any]] = []
        for rec in rows:
            sq = str(rec.get("squawk") or "").strip().zfill(4)
            if sq not in EMERGENCY_SQUAWKS:
                continue
            events.append(
                {
                    "ts_utc": rec.get("ts_utc"),
                    "hex": rec.get("hex"),
                    "callsign": rec.get("callsign"),
                    "squawk": sq,
                    "lat": rec.get("lat"),
                    "lon": rec.get("lon"),
                    "altitude_ft": rec.get("altitude_ft"),
                    "caveat": "Observed ADS-B squawk from our antenna — not confirmed by ATC",
                }
            )
        return events


_store: Optional[AdsbHistoryStore] = None


def get_adsb_history() -> AdsbHistoryStore:
    global _store
    if _store is None:
        _store = AdsbHistoryStore()
    return _store

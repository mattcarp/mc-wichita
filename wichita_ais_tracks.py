"""AIS position snapshot ring buffer (JSONL) for harbour replay and activity charts."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

def _track_hours() -> float:
    return float(os.environ.get("WICHITA_AIS_TRACK_HOURS", "48"))


def _max_file_bytes() -> int:
    return int(os.environ.get("WICHITA_AIS_SNAPSHOT_MAX_BYTES", str(64 * 1024 * 1024)))


def snapshots_dir() -> Path:
    raw = os.environ.get("WICHITA_AIS_SNAPSHOTS_DIR", "~/wichita/live/ais_snapshots").strip()
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _snapshot_path() -> Path:
    return snapshots_dir() / "snapshots.jsonl"


class AisSnapshotStore:
    """Append-only harbour snapshots; each line is one poll of all vessels."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def record_ships(self, ships: List[Dict[str, Any]], ts: Optional[datetime] = None) -> None:
        if not ships:
            return
        ts = ts or datetime.now(timezone.utc)
        compact = []
        for s in ships:
            if s.get("is_base_station"):
                continue
            lat, lon = s.get("lat"), s.get("lon")
            if lat is None or lon is None:
                continue
            compact.append(
                {
                    "mmsi": int(s["mmsi"]),
                    "lat": float(lat),
                    "lon": float(lon),
                    "speed_kn": s.get("speed_kn"),
                    "cog_deg": s.get("cog_deg"),
                    "display_name": s.get("display_name"),
                    "shiptype_category": s.get("shiptype_category") or "other",
                    "shiptype_label": s.get("shiptype_label"),
                }
            )
        if not compact:
            return
        row = {"ts_utc": ts.isoformat(), "ships": compact}
        with self._lock:
            self._append(row, ts)

    def _append(self, row: Dict[str, Any], ts: datetime) -> None:
        path = _snapshot_path()
        line = json.dumps(row, ensure_ascii=False) + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        self._trim(path, ts)

    def _trim(self, path: Path, now: datetime) -> None:
        cutoff = now - timedelta(hours=_track_hours())
        try:
            if path.stat().st_size <= _max_file_bytes():
                # Still drop lines older than retention even under byte cap.
                pass
        except OSError:
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        kept: List[str] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                t = datetime.fromisoformat(rec["ts_utc"].replace("Z", "+00:00"))
            except (KeyError, ValueError, json.JSONDecodeError):
                continue
            if t >= cutoff:
                kept.append(line)
        if len(kept) < len(lines) or path.stat().st_size > _max_file_bytes():
            while kept and len("\n".join(kept)) > _max_file_bytes():
                kept.pop(0)
            path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    def _read_rows(self, hours: float) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        path = _snapshot_path()
        out: List[Dict[str, Any]] = []
        if not path.is_file():
            return out
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                t = datetime.fromisoformat(rec["ts_utc"].replace("Z", "+00:00"))
                if t >= cutoff:
                    out.append(rec)
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            pass
        out.sort(key=lambda r: r.get("ts_utc", ""))
        return out

    def timeline_meta(self, hours: Optional[float] = None) -> Dict[str, Any]:
        hours = hours or _track_hours()
        rows = self._read_rows(hours)
        if not rows:
            return {
                "hours": hours,
                "first_ts_utc": None,
                "last_ts_utc": None,
                "snapshot_count": 0,
            }
        return {
            "hours": hours,
            "first_ts_utc": rows[0]["ts_utc"],
            "last_ts_utc": rows[-1]["ts_utc"],
            "snapshot_count": len(rows),
        }

    def snapshot_nearest(self, ts_utc: str, max_delta_s: float = 120.0) -> Optional[Dict[str, Any]]:
        try:
            target = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        rows = self._read_rows(_track_hours())
        best: Optional[Tuple[float, Dict[str, Any]]] = None
        for row in rows:
            try:
                t = datetime.fromisoformat(row["ts_utc"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            delta = abs((t - target).total_seconds())
            if delta > max_delta_s:
                continue
            if best is None or delta < best[0]:
                best = (delta, row)
        if best is None:
            return None
        return {**best[1], "delta_s": best[0]}

    def activity_by_type(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Unique MMSI heard per UTC hour, grouped by shiptype_category."""
        now = datetime.now(timezone.utc)
        hour_buckets: List[Dict[str, Set[int]]] = [
            {} for _ in range(hours)
        ]
        rows = self._read_rows(float(hours))
        for row in rows:
            try:
                t = datetime.fromisoformat(row["ts_utc"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            age_h = (now - t.astimezone(timezone.utc)).total_seconds() / 3600.0
            if age_h < 0 or age_h >= hours:
                continue
            idx = hours - 1 - int(age_h)
            for ship in row.get("ships") or []:
                mmsi = ship.get("mmsi")
                if mmsi is None:
                    continue
                cat = ship.get("shiptype_category") or "other"
                hour_buckets[idx].setdefault(cat, set()).add(int(mmsi))
        result: List[Dict[str, Any]] = []
        for i in range(hours):
            hour_start = now - timedelta(hours=(hours - 1 - i))
            by_type = {k: len(v) for k, v in hour_buckets[i].items()}
            total = sum(by_type.values())
            result.append(
                {
                    "hour_utc": hour_start.strftime("%Y-%m-%dT%H:00"),
                    "vessels_total": total,
                    "by_type": by_type,
                }
            )
        return result


_store: Optional[AisSnapshotStore] = None


def get_snapshot_store() -> AisSnapshotStore:
    global _store
    if _store is None:
        _store = AisSnapshotStore()
    return _store

"""Director-style incident replay scenes from heard-timeline JSONL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from wichita_live_events import events_dir

MALTA_CENTER = {"lat": 35.8987, "lon": 14.5145, "zoom": 12}


def _load_events(hours: float, limit: int = 500) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: List[Dict[str, Any]] = []
    root = events_dir()
    for path in sorted(root.glob("events-*.jsonl")):
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
    if len(out) > limit:
        out = out[-limit:]
    return out


def _camera_for_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    lat = ev.get("lat")
    lon = ev.get("lon")
    if lat is not None and lon is not None:
        return {"lat": lat, "lon": lon, "zoom": 13}
    return dict(MALTA_CENTER)


def build_scene(hours: float = 6.0) -> Dict[str, Any]:
    events = _load_events(hours)
    start = events[0]["ts_utc"] if events else None
    end = events[-1]["ts_utc"] if events else None
    beats = []
    for ev in events:
        beats.append(
            {
                "ts_utc": ev.get("ts_utc"),
                "kind": ev.get("kind"),
                "sentence": ev.get("sentence"),
                "mmsi": ev.get("mmsi"),
                "camera": _camera_for_event(ev),
            }
        )
    return {
        "title": "Heard timeline replay",
        "caveat": "Observed radio traffic from our antenna — not official records or ground truth",
        "map_center": MALTA_CENTER,
        "start_utc": start,
        "end_utc": end,
        "beats": beats,
    }


def export_bundle(hours: float = 6.0) -> Dict[str, Any]:
    scene = build_scene(hours)
    return {
        "format": "wichita-incident-replay-v1",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "scene": scene,
        "static": True,
    }

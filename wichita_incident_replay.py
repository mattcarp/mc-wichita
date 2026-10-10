"""Director-style incident replay scenes from real Heard-timeline events."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from wichita_adsb_tracks import OBSERVED_CAVEAT
from wichita_live_events import get_engine

MALTA_CAMERA = {
    "center_lat": 35.8987,
    "center_lon": 14.5145,
    "default_zoom": "harbour",
    "label": "Offline Malta map (not for navigation)",
}


def export_dir() -> Path:
    raw = os.environ.get("WICHITA_INCIDENT_EXPORT_DIR", "~/wichita/incident_exports").strip()
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _event_ts(ev: Dict[str, Any]) -> datetime:
    return datetime.fromisoformat(ev["ts_utc"].replace("Z", "+00:00"))


def _camera_shot(lat: Optional[float], lon: Optional[float], label: str, at_utc: str) -> Dict[str, Any]:
    return {
        "at_utc": at_utc,
        "label": label,
        "camera": {
            **MALTA_CAMERA,
            "focus_lat": lat or MALTA_CAMERA["center_lat"],
            "focus_lon": lon or MALTA_CAMERA["center_lon"],
        },
    }


def build_scene_from_event(event: Dict[str, Any], window_min: int = 30) -> Dict[str, Any]:
    ts = _event_ts(event)
    start = ts - timedelta(minutes=window_min)
    end = ts + timedelta(minutes=window_min)
    engine = get_engine()
    related = [
        ev
        for ev in engine.read_events(hours=72)
        if start <= _event_ts(ev) <= end
    ]
    related.sort(key=lambda e: e.get("ts_utc", ""))
    shots: List[Dict[str, Any]] = []
    for ev in related:
        shots.append(
            _camera_shot(
                ev.get("lat"),
                ev.get("lon"),
                ev.get("sentence") or ev.get("kind") or "Event",
                ev.get("ts_utc") or ts.isoformat(),
            )
        )
    if not shots:
        shots.append(_camera_shot(None, None, event.get("sentence") or "Incident", ts.isoformat()))
    scene_id = f"{event.get('kind', 'event')}-{ts.strftime('%Y%m%dT%H%M%SZ')}"
    return {
        "scene_id": scene_id,
        "title": event.get("sentence") or scene_id,
        "anchor_event": event,
        "timeline": {
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "anchor_utc": ts.isoformat(),
        },
        "shots": shots,
        "data_packs": {"events": related},
        "caveat": OBSERVED_CAVEAT,
        "map": MALTA_CAMERA,
        "export_hint": "Static JSON bundle for sottosound.com hosting",
    }


def scene_by_ts(ts_utc: str) -> Optional[Dict[str, Any]]:
    engine = get_engine()
    target = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
    for ev in engine.read_events(hours=72):
        if _event_ts(ev) == target:
            return build_scene_from_event(ev)
    for ev in engine.read_events(hours=72):
        if ev.get("ts_utc", "").startswith(ts_utc[:19]):
            return build_scene_from_event(ev)
    return None


def write_export_bundle(scene: Dict[str, Any]) -> Path:
    out = export_dir() / f"{scene['scene_id']}.json"
    out.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

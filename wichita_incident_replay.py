"""Incident replay: time-synced AIS, ADS-B, weather, assist context, and retained voice clips."""

from __future__ import annotations

import json
import math
import os
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import wichita_adsb_tracks as wat
import wichita_ais_tracks as ais_tracks
import wichita_ground_voice as gv
import wichita_malta_weather as wmw
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


def _parse_ts(ts_utc: str) -> datetime:
    return datetime.fromisoformat(ts_utc.replace("Z", "+00:00")).astimezone(timezone.utc)


def _event_ts(ev: Dict[str, Any]) -> datetime:
    return _parse_ts(ev["ts_utc"])


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _nm(meters: float) -> float:
    return meters / 1852.0


def _clip_duration_sec(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            rate = w.getframerate() or 8000
            return w.getnframes() / float(rate)
    except (wave.Error, OSError):
        return 0.0


def voice_clips_in_window(start: datetime, end: datetime, base: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retained SDR voice clips (score >= 70) on allowlisted channels only."""
    base = base or gv._events_dir()
    gv.purge_expired(base)
    out: List[Dict[str, Any]] = []
    for ev in gv.read_events(base):
        if not ev.get("flagged") or not ev.get("clip"):
            continue
        ch_id = ev.get("channel_id") or ""
        if ch_id not in gv.CHANNELS:
            continue
        try:
            started = float(ev["started_at"])
        except (KeyError, TypeError, ValueError):
            continue
        ts = datetime.fromtimestamp(started, tz=timezone.utc)
        if ts < start or ts > end:
            continue
        clip_name = Path(str(ev["clip"])).name
        clip_path = gv.resolve_clip_path(clip_name, base=base)
        if clip_path is None:
            continue
        ch = gv.CHANNELS[ch_id]
        duration = _clip_duration_sec(clip_path)
        out.append(
            {
                "clip_id": clip_name,
                "channel_id": ch_id,
                "channel_name": ch.name,
                "band": ch.band,
                "frequency_mhz": ch.frequency_mhz,
                "started_at_utc": ts.isoformat(),
                "duration_sec": round(duration, 3),
                "stress_score": ev.get("stress_score"),
                "playback_url": f"/api/incident-replay/clips/{clip_name}",
            }
        )
    out.sort(key=lambda c: c.get("started_at_utc") or "")
    return out


def _weather_context(ts: datetime) -> Dict[str, Any]:
    bundle = wmw.malta_weather_bundle()
    hourly = bundle.get("hourly") or {}
    times = hourly.get("time") or []
    label = bundle.get("plain_english") or "Weather unavailable."
    matched = None
    for i, t in enumerate(times):
        try:
            ht = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
            if ht.tzinfo is None:
                ht = ht.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if abs((ht - ts).total_seconds()) < 3600:
            matched = i
            break
    if matched is not None and hourly.get("wind_speed_10m"):
        try:
            w_kn = float(hourly["wind_speed_10m"][matched]) * 0.539957
            wave_h = (hourly.get("wave_height") or [None])[matched]
            parts = [f"Wind about {w_kn:.0f} kn near replay time"]
            if wave_h is not None:
                parts.append(f"seas around {float(wave_h):.1f} m")
            label = ", ".join(parts) + "."
        except (TypeError, ValueError, IndexError):
            pass
    return {
        "plain_english": label,
        "flags": bundle.get("flags") or {},
        "attribution": bundle.get("attribution"),
        "source": bundle.get("source", "open-meteo"),
        "note": "Hourly Open-Meteo values nearest the replay cursor; not a certified forecast archive.",
    }


def nearest_assist(
    lat: Optional[float],
    lon: Optional[float],
    ships: List[Dict[str, Any]],
    aircraft: List[Dict[str, Any]],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    if lat is None or lon is None:
        return []
    candidates: List[Tuple[float, Dict[str, Any]]] = []
    for s in ships:
        slat, slon = s.get("lat"), s.get("lon")
        if slat is None or slon is None:
            continue
        dist = _haversine_m(lat, lon, float(slat), float(slon))
        candidates.append(
            (
                dist,
                {
                    "kind": "vessel",
                    "label": s.get("display_name") or f"MMSI {s.get('mmsi')}",
                    "distance_nm": round(_nm(dist), 2),
                    "mmsi": s.get("mmsi"),
                    "speed_kn": s.get("speed_kn"),
                },
            )
        )
    for p in aircraft:
        plat, plon = p.get("lat"), p.get("lon")
        if plat is None or plon is None:
            continue
        dist = _haversine_m(lat, lon, float(plat), float(plon))
        candidates.append(
            (
                dist,
                {
                    "kind": "aircraft",
                    "label": p.get("callsign") or p.get("hex") or "Aircraft",
                    "distance_nm": round(_nm(dist), 2),
                    "hex": p.get("hex"),
                    "squawk": p.get("squawk"),
                    "altitude_ft": p.get("altitude_ft"),
                },
            )
        )
    candidates.sort(key=lambda x: x[0])
    return [c[1] for c in candidates[:limit]]


def replay_frame(
    ts_utc: str,
    anchor_utc: str,
    window_min: int = 30,
    max_delta_s: float = 120.0,
) -> Optional[Dict[str, Any]]:
    anchor = _parse_ts(anchor_utc)
    try:
        cursor = _parse_ts(ts_utc)
    except (TypeError, ValueError):
        return None
    start = anchor - timedelta(minutes=window_min)
    end = anchor + timedelta(minutes=window_min)
    if cursor < start or cursor > end:
        return None

    ais = ais_tracks.get_snapshot_store().snapshot_nearest(ts_utc, max_delta_s=max_delta_s)
    ships = (ais or {}).get("ships") or []
    aircraft = wat.get_track_store().snapshot_nearest(ts_utc, max_delta_s=max_delta_s)

    focus_lat = None
    focus_lon = None
    for ev in get_engine().read_events(hours=72):
        if _event_ts(ev) == anchor:
            focus_lat = ev.get("lat")
            focus_lon = ev.get("lon")
            break
    if focus_lat is None:
        focus_lat = MALTA_CAMERA["center_lat"]
        focus_lon = MALTA_CAMERA["center_lon"]

    clips = voice_clips_in_window(start, end)
    active_voice: List[str] = []
    for clip in clips:
        try:
            cts = _parse_ts(clip["started_at_utc"])
        except (KeyError, ValueError):
            continue
        end_clip = cts + timedelta(seconds=float(clip.get("duration_sec") or 0))
        if cts <= cursor <= end_clip:
            active_voice.append(clip["clip_id"])

    return {
        "ts_utc": cursor.isoformat(),
        "anchor_utc": anchor.isoformat(),
        "ships": ships,
        "aircraft": aircraft,
        "weather": _weather_context(cursor),
        "nearest_assist": nearest_assist(focus_lat, focus_lon, ships, aircraft),
        "voice_active_clip_ids": active_voice,
        "voice_clips": clips,
        "caveat": OBSERVED_CAVEAT,
    }


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
    related = [ev for ev in engine.read_events(hours=72) if start <= _event_ts(ev) <= end]
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
    clips = voice_clips_in_window(start, end)
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
        "voice_clips": clips,
        "voice_clip_count": len(clips),
        "data_packs": {"events": related},
        "caveat": OBSERVED_CAVEAT,
        "map": MALTA_CAMERA,
        "export_hint": "Static JSON bundle for sottosound.com hosting",
    }


def scene_by_ts(ts_utc: str) -> Optional[Dict[str, Any]]:
    engine = get_engine()
    target = _parse_ts(ts_utc)
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

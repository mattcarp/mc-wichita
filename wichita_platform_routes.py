"""Routes for weather, watch zones, incident replay, and combined feed health."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import wichita_adsb_live as wad
import wichita_adsb_tracks as wat
import wichita_ais_live as wal
import wichita_ground_voice as gv
import wichita_incident_replay as wir
import wichita_malta_weather as wmw
import wichita_receiver_health as wrh
import wichita_watch_zones as wwz

router = APIRouter(tags=["platform"])


class WatchZoneBody(BaseModel):
    id: str
    name: str
    polygon: List[List[float]] = Field(..., description="[[lon, lat], ...] closed ring")


@router.get("/api/feed-health")
def feed_health():
    ais = wal.cached_dashboard_bundle()
    adsb = wad.live_adsb_snapshot()
    ships = ais.get("ships") or []
    planes = adsb.get("aircraft") or []
    youngest_ais = min((s.get("last_signal_s") for s in ships if s.get("last_signal_s") is not None), default=None)
    youngest_adsb = min((p.get("last_signal_s") for p in planes if p.get("last_signal_s") is not None), default=None)
    ais_h = wrh.feed_health_payload(
        receiver="AIS-catcher",
        band="AIS 161.975 / 162.025 MHz",
        online=bool(ais.get("online")),
        error=ais.get("error"),
        youngest_signal_s=youngest_ais,
        entity_count=len(ships),
    )
    adsb_h = wrh.feed_health_payload(
        receiver="readsb" if adsb.get("local_antenna_connected") else "adsb.lol",
        band="ADS-B 1090 MHz",
        online=bool(adsb.get("receiver_connected")),
        error=adsb.get("error"),
        youngest_signal_s=youngest_adsb,
        entity_count=len(planes),
    )
    badge = wrh.heard_last_60s_badge(
        ais_count=wrh.count_heard_within(ships),
        adsb_count=wrh.count_heard_within(
            [p for p in planes if p.get("source") in (wad.SRC_LOCAL, wad.SRC_BOTH)]
        ),
    )
    return {"ais": ais_h, "adsb": adsb_h, "heard_badge": badge}


@router.get("/api/malta/weather")
def malta_weather():
    return wmw.malta_weather_bundle()


@router.get("/api/sky/adsb/tracks/{hex_id}")
async def adsb_track(hex_id: str, hours: Optional[float] = None):
    track = wat.get_track_store().track_for_hex(hex_id, hours=hours)
    return {"hex": hex_id.lower(), "points": track, "caveat": wat.OBSERVED_CAVEAT}


@router.get("/api/sky/adsb/emergency-replays")
async def adsb_emergency_replays(hours: Optional[float] = None):
    return {"replays": wat.get_track_store().emergency_replays(hours=hours), "caveat": wat.OBSERVED_CAVEAT}


@router.get("/api/incident-replay/scene")
async def incident_scene(ts_utc: str):
    scene = wir.scene_by_ts(ts_utc)
    if scene is None:
        raise HTTPException(status_code=404, detail="event not found for timestamp")
    return scene


@router.get("/api/incident-replay/frame")
async def incident_frame(ts_utc: str, anchor_utc: str, window_min: int = 30):
    frame = wir.replay_frame(ts_utc, anchor_utc, window_min=window_min)
    if frame is None:
        raise HTTPException(status_code=404, detail="time outside incident replay window")
    return frame


@router.get("/api/incident-replay/clips/{clip_name}")
async def incident_replay_clip(clip_name: str):
    """Retained receive-only clips (score >= 70, <= 72 h). Clerk session required."""
    if not gv.legally_cleared():
        raise HTTPException(status_code=409, detail="Ground voice not cleared")
    path = gv.resolve_clip_path(clip_name)
    if path is None:
        raise HTTPException(status_code=404, detail="clip not found or expired")
    return FileResponse(str(path), media_type="audio/wav", filename=path.name, headers={"Cache-Control": "no-store"})


@router.post("/api/incident-replay/export")
async def incident_export(ts_utc: str):
    scene = wir.scene_by_ts(ts_utc)
    if scene is None:
        raise HTTPException(status_code=404, detail="event not found")
    path = wir.write_export_bundle(scene)
    return {"scene_id": scene["scene_id"], "path": str(path), "scene": scene}


@router.get("/api/watch-zones")
async def watch_zones_list():
    return {"zones": wwz.list_zones()}


@router.put("/api/watch-zones")
async def watch_zones_put(body: WatchZoneBody):
    if len(body.polygon) < 3:
        raise HTTPException(status_code=400, detail="polygon needs at least 3 points")
    zone = wwz.upsert_zone(body.model_dump())
    return zone


@router.delete("/api/watch-zones/{zone_id}")
async def watch_zones_delete(zone_id: str):
    if not wwz.delete_zone(zone_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": zone_id}

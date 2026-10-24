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
import wichita_interest as wi
import wichita_aircraft_interest as wai
import wichita_ais_live as wal

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


class InterestLookupBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=120)


class InterestBoatBody(BaseModel):
    mmsi: int
    label: Optional[str] = None
    callsign: Optional[str] = None
    imo: Optional[int] = None
    note: Optional[str] = None


@router.get("/api/interests/boats")
async def interests_boats_list():
    return {"boats": wi.list_boats(), "schema_version": 1}


@router.post("/api/interests/boats/lookup")
async def interests_boats_lookup(body: InterestLookupBody):
    bundle = wal.cached_dashboard_bundle()
    ships = bundle.get("ships") or []
    return {"candidates": wi.lookup_boat_candidates(body.query, ships)}


@router.post("/api/interests/boats")
async def interests_boats_add(body: InterestBoatBody):
    try:
        boat = wi.add_boat(
            mmsi=body.mmsi,
            label=body.label,
            callsign=body.callsign,
            imo=body.imo,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return boat


@router.delete("/api/interests/boats/{boat_id}")
async def interests_boats_delete(boat_id: str):
    if not wi.remove_boat(boat_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": boat_id}


class InterestFlightBody(BaseModel):
    hex: Optional[str] = Field(None, max_length=12)
    callsign: Optional[str] = Field(None, max_length=32)
    registration: Optional[str] = Field(None, max_length=32)
    label: Optional[str] = Field(None, max_length=120)
    note: Optional[str] = Field(None, max_length=500)


@router.get("/api/interests")
async def interests_summary():
    """Things-of-interest summary for external consumers (e.g. Matt's World View)."""
    return {
        "schema_version": 1,
        "boats": wi.list_boats(),
        "flights": wi.list_flights(),
        "aircraft_rules": wai.list_aircraft_rules(),
        "station": {"lat": wai.STATION_LAT, "lon": wai.STATION_LON, "label": "Valletta station (50 Archbishop St)"},
    }


@router.get("/api/interests/flights")
async def interests_flights_list():
    return {"flights": wi.list_flights(), "aircraft_rules": wai.list_aircraft_rules(), "schema_version": 1}


@router.post("/api/interests/flights/lookup")
async def interests_flights_lookup(body: InterestLookupBody):
    snap = wad.live_adsb_snapshot()
    planes = snap.get("aircraft") or []
    return {"candidates": wai.lookup_aircraft_candidates(body.query, planes)}


@router.post("/api/interests/flights")
async def interests_flights_add(body: InterestFlightBody):
    try:
        flight = wai.add_flight(
            hex_id=body.hex,
            callsign=body.callsign,
            registration=body.registration,
            label=body.label,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return flight


@router.delete("/api/interests/flights/{flight_id}")
async def interests_flights_delete(flight_id: str):
    if not wai.remove_flight(flight_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": flight_id}


@router.get("/api/interests/aircraft/rules")
async def interests_aircraft_rules_get():
    return {"rules": wai.list_aircraft_rules()}


class AircraftRulesBody(BaseModel):
    rules: List[Dict[str, Any]]


@router.put("/api/interests/aircraft/rules")
async def interests_aircraft_rules_put(body: AircraftRulesBody):
    if not body.rules:
        raise HTTPException(status_code=400, detail="rules required")
    return {"rules": wai.save_aircraft_rules(body.rules)}

"""GEV Oct updates: weather, ADSB history, replay, watch zones, receivers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import wichita_adsb_live as wad
import wichita_ais_live as wal
from wichita_adsb_history import get_adsb_history
from wichita_incident_replay import build_scene, export_bundle
from wichita_malta_weather import malta_weather_card
from wichita_watch_zones import delete_zone, list_zones, upsert_zone

router = APIRouter(prefix="/api/gev", tags=["gev"])


@router.get("/receivers")
async def receivers_status():
    ships_raw, err_ships = wal.fetch_ais_json("/api/ships.json")
    stat_raw, err_stat = wal.fetch_ais_json("/api/stat.json")
    ships = (ships_raw or {}).get("ships") or []
    online_ais = ships_raw is not None and err_ships is None
    ais_health = wal.receiver_health(stat_raw, online_ais, ships, err_ships or err_stat)
    adsb = wad.live_adsb_snapshot()
    return {
        "ais": ais_health,
        "adsb": adsb.get("receiver_health"),
        "caveat": "Live feeds from our receive-only antenna — not navigation or SAR authority data",
    }


@router.get("/weather/malta")
async def malta_weather():
    return malta_weather_card()


@router.get("/adsb/history")
async def adsb_history(hours: float = 24.0, hex_id: Optional[str] = None):
    store = get_adsb_history()
    return {
        "hours": hours,
        "positions": store.positions_since(hours=hours, hex_id=hex_id),
        "caveat": "Observed ADS-B positions from our antenna — not official flight data",
    }


@router.get("/adsb/emergency-replay")
async def adsb_emergency(hours: float = 48.0):
    store = get_adsb_history()
    return {
        "hours": hours,
        "events": store.emergency_replay(hours=hours),
        "caveat": "Emergency squawks heard over ADS-B — unverified, not ground truth",
    }


@router.get("/replay/scene")
async def replay_scene(hours: float = 6.0):
    return build_scene(hours=hours)


@router.get("/replay/export")
async def replay_export(hours: float = 6.0):
    return export_bundle(hours=hours)


@router.get("/watch-zones")
async def watch_zones_list():
    return {"zones": list_zones()}


class WatchZoneBody(BaseModel):
    name: str = Field(default="Watch zone")
    polygon: List[List[float]]
    id: Optional[str] = None


@router.post("/watch-zones")
async def watch_zones_save(body: WatchZoneBody):
    try:
        rec = upsert_zone(body.name, body.polygon, body.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return rec


@router.delete("/watch-zones/{zone_id}")
async def watch_zones_remove(zone_id: str):
    if not delete_zone(zone_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": zone_id}

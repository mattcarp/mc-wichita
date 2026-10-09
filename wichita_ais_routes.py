"""Read-only FastAPI routes proxying AIS-catcher for the live harbour panel."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import wichita_ais_live as wal

router = APIRouter(prefix="/api/live-ais", tags=["live-ais"])


@router.get("/snapshot")
async def live_ais_snapshot():
    """Ship list, tracks, and receiver status in one poll-friendly payload."""
    return wal.live_dashboard_bundle()


@router.get("/status")
async def live_ais_status():
    ships_raw, err = wal.fetch_ais_json("/api/ships.json")
    stat_raw, _ = wal.fetch_ais_json("/api/stat.json")
    ships = (ships_raw or {}).get("ships") or []
    online = ships_raw is not None
    return wal.live_status_payload(stat_raw, ships, online, err)


@router.get("/ships/{mmsi}")
async def live_ais_ship(mmsi: int):
    detail, err = wal.live_ship_detail(mmsi)
    if detail is None:
        raise HTTPException(status_code=503 if err == "receiver offline" else 404, detail=err or "not found")
    return detail

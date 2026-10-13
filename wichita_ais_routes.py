"""Read-only FastAPI routes proxying AIS-catcher for the live harbour panel."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException

import wichita_ais_live as wal
import wichita_ais_tracks as wat
import wichita_captures as wc
from wichita_ais_voice import voice_channel_tiles
from wichita_live_events import get_engine

router = APIRouter(prefix="/api/live-ais", tags=["live-ais"])


@router.get("/snapshot")
async def live_ais_snapshot():
    """Ship list, tracks, and receiver status in one poll-friendly payload."""
    return await asyncio.to_thread(wal.cached_dashboard_bundle)


@router.get("/status")
async def live_ais_status():
    ships_raw, err = wal.fetch_ais_json("/api/ships.json")
    stat_raw, _ = wal.fetch_ais_json("/api/stat.json")
    ships = (ships_raw or {}).get("ships") or []
    online = ships_raw is not None
    return wal.live_status_payload(stat_raw, ships, online, err)


@router.get("/mmsi/{mmsi}")
async def live_ais_mmsi_lookup(mmsi: int):
    """In-app MMSI lookup: decoded digits + ITU MID country + AIS static data heard by our receiver."""
    return wal.wichita_mmsi.lookup(mmsi, None, wal.shiptype_label)


@router.get("/ships/{mmsi}")
async def live_ais_ship(mmsi: int):
    detail, err = wal.live_ship_detail(mmsi)
    if detail is None:
        raise HTTPException(status_code=503 if err == "receiver offline" else 404, detail=err or "not found")
    return detail


@router.get("/events")
async def live_ais_events(hours: int = 2, limit: int = 20, before: str | None = None):
    engine = get_engine()
    return engine.events_page(hours=hours, limit=limit, before=before)


@router.get("/history/meta")
async def live_ais_history_meta(hours: float | None = None):
    store = wat.get_snapshot_store()
    return store.timeline_meta(hours=hours)


@router.get("/history/at")
async def live_ais_history_at(ts_utc: str, max_delta_s: float = 120.0):
    snap = wat.get_snapshot_store().snapshot_nearest(ts_utc, max_delta_s=max_delta_s)
    if snap is None:
        raise HTTPException(status_code=404, detail="no snapshot near requested time")
    return snap


@router.get("/activity")
async def live_ais_activity(hours: int = 24):
    if hours not in (24, 168):
        raise HTTPException(status_code=400, detail="hours must be 24 or 168")
    return {
        "hours": hours,
        "buckets": wat.get_snapshot_store().activity_by_type(hours=hours),
        "caveat": "Counts unique MMSI heard per hour from stored AIS snapshots — incomplete if receiver was offline.",
    }


@router.get("/voice-watch")
async def live_voice_watch():
    voice_live = os.environ.get("WICHITA_VOICE_LIVE", "0").strip().lower() in ("1", "true", "yes")
    roots = wc.captures_roots_from_env()
    refs = wc.scan_captures(roots)
    ag = wc.dashboard_aggregate(refs)
    detail = None
    if ag.get("available") and ag.get("primary_capture_id"):
        ref = wc.resolve_capture(ag["primary_capture_id"], roots)
        if ref is not None:
            detail = wc.capture_detail(ref)
    label = ""
    time_utc = None
    if detail:
        label = detail.get("picker_label") or detail.get("capture_id") or ""
        time_utc = detail.get("start_utc")
    tiles = voice_channel_tiles(
        (detail or {}).get("marine_watch"),
        ((detail or {}).get("airband") or {}).get("watch"),
        label,
        time_utc,
        voice_live,
    )
    return {"voice_live": voice_live, "channels": tiles}

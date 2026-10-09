"""Read-only routes for ADS-B and satellite pass layers."""

from __future__ import annotations

from fastapi import APIRouter

import wichita_adsb_live as wad
import wichita_satellites as wsat

router = APIRouter(prefix="/api/sky", tags=["sky"])


@router.get("/adsb/snapshot")
async def adsb_snapshot():
    return wad.live_adsb_snapshot()


@router.get("/satellites")
async def satellites_overview():
    return wsat.satellite_overview()

"""Read-only routes for ADS-B and satellite pass layers."""

from __future__ import annotations

from fastapi import APIRouter

import wichita_adsb_live as wad
import wichita_aircraft_interest as wai
import wichita_satellites as wsat

router = APIRouter(prefix="/api/sky", tags=["sky"])


@router.get("/adsb/snapshot")
def adsb_snapshot():
    return wai.enrich_adsb_snapshot(wad.live_adsb_snapshot())


@router.get("/satellites")
def satellites_overview():
    return wsat.satellite_overview()

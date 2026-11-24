"""Airband metadata and LMML channel table (receive-only)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from wichita_airband_adsb import guess_payload
from wichita_airband_channel import load_lmml_channels

router = APIRouter(prefix="/api/airband", tags=["airband"])


@router.get("/lmml/channels")
def lmml_channels() -> Dict[str, Any]:
    return load_lmml_channels()


@router.get("/lmml/guess")
def lmml_guess(freq_mhz: float, event_time_utc: Optional[str] = None) -> Dict[str, Any]:
    return guess_payload(freq_mhz, event_time_utc=event_time_utc)
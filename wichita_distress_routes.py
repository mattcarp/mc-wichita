"""API routes for offline distress replay and health."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from wichita_distress import decode_dsc_file, decode_epirb_file, replay_capture

router = APIRouter(prefix="/api/distress", tags=["distress"])


class ReplayBody(BaseModel):
    path: str = Field(..., description="Absolute or repo-relative path to .wav, .sdriq, or HackRF .iq")
    sample_rate_hz: float | None = Field(
        default=None, description="Required for raw cs8 IQ without sdriq header"
    )


@router.get("/health")
def distress_health():
    return {
        "dsc_ch70_mhz": 156.525,
        "epirb_mhz": 406.028,
        "receive_only": True,
        "offline_iq": ["hackrf_cs8", "sdriq", "sdrplay_cs16"],
    }


@router.post("/replay")
async def distress_replay(body: ReplayBody):
    p = Path(body.path).expanduser()
    if not p.is_file():
        raise HTTPException(status_code=404, detail="capture file not found")
    if body.sample_rate_hz:
        import os

        os.environ["WICHITA_IQ_SAMPLE_RATE"] = str(body.sample_rate_hz)
    return await asyncio.to_thread(replay_capture, p)


@router.post("/decode/dsc")
async def distress_decode_dsc(body: ReplayBody):
    p = Path(body.path).expanduser()
    if not p.is_file():
        raise HTTPException(status_code=404, detail="capture file not found")
    if body.sample_rate_hz:
        import os

        os.environ["WICHITA_IQ_SAMPLE_RATE"] = str(body.sample_rate_hz)
    messages = await asyncio.to_thread(decode_dsc_file, p)
    return {"messages": messages, "count": len(messages)}


@router.post("/decode/epirb")
async def distress_decode_epirb(body: ReplayBody):
    p = Path(body.path).expanduser()
    if not p.is_file():
        raise HTTPException(status_code=404, detail="capture file not found")
    if body.sample_rate_hz:
        import os

        os.environ["WICHITA_IQ_SAMPLE_RATE"] = str(body.sample_rate_hz)
    messages = await asyncio.to_thread(decode_epirb_file, p)
    return {"messages": messages, "count": len(messages)}

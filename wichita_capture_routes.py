"""FastAPI routes for read-only Wichita capture library."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

import wichita_captures as wc

router = APIRouter(prefix="/api/capture-feed", tags=["capture-feed"])


def _roots() -> List[Path]:
    return wc.captures_roots_from_env()


@router.get("")
async def list_capture_feed():
    refs = wc.scan_captures(_roots())
    return {
        "roots": [str(p) for p in _roots()],
        "count": len(refs),
        "captures": [wc.capture_summary(r) for r in refs],
    }


@router.get("/dashboard")
async def capture_dashboard():
    return wc.dashboard_aggregate(wc.scan_captures(_roots()))


@router.get("/{capture_id}")
async def get_capture(capture_id: str):
    ref = wc.resolve_capture(capture_id, _roots())
    if ref is None:
        raise HTTPException(status_code=404, detail="Capture folder not found")
    return wc.capture_detail(ref)


@router.get("/{capture_id}/wideband-psd")
async def get_wideband_psd(capture_id: str, max_points: int = 2048):
    ref = wc.resolve_capture(capture_id, _roots())
    if ref is None:
        raise HTTPException(status_code=404, detail="Capture folder not found")
    payload = wc.load_wideband_psd(ref.path, max_points=max_points)
    analysis = wc._read_json(ref.path / "analysis_report.json") or {}
    if payload.get("available"):
        payload["median_db"] = analysis.get("wideband_psd_median_db")
    return payload


@router.get("/{capture_id}/ais")
async def get_ais(capture_id: str):
    ref = wc.resolve_capture(capture_id, _roots())
    if ref is None:
        raise HTTPException(status_code=404, detail="Capture folder not found")
    analysis = wc._read_json(ref.path / "analysis_report.json") or {}
    messages = wc.decode_ais_from_nmea(ref.path, analysis)
    return {"capture_id": capture_id, "messages": messages, "count": len(messages)}


@router.get("/{capture_id}/marine-watch")
async def get_marine_watch(capture_id: str):
    ref = wc.resolve_capture(capture_id, _roots())
    if ref is None:
        raise HTTPException(status_code=404, detail="Capture folder not found")
    analysis = wc._read_json(ref.path / "analysis_report.json") or {}
    return wc.marine_watch_payload(ref.path, analysis)


@router.get("/{capture_id}/airband")
async def get_airband(capture_id: str):
    ref = wc.resolve_capture(capture_id, _roots())
    if ref is None:
        raise HTTPException(status_code=404, detail="Capture folder not found")
    return wc.airband_payload(ref.path)


@router.get("/{capture_id}/timeline")
async def get_timeline(capture_id: str):
    ref = wc.resolve_capture(capture_id, _roots())
    if ref is None:
        raise HTTPException(status_code=404, detail="Capture folder not found")
    detail = wc.capture_detail(ref)
    return {"capture_id": capture_id, "events": detail.get("timeline") or []}


@router.get("/{capture_id}/files/{filename}")
async def get_capture_file(capture_id: str, filename: str, request: Request):
    ref = wc.resolve_capture(capture_id, _roots())
    if ref is None:
        raise HTTPException(status_code=404, detail="Capture folder not found")
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = ref.path / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not present in this capture folder")
    media_type = "audio/wav" if safe_name.lower().endswith(".wav") else "application/octet-stream"
    range_header = request.headers.get("range")
    if range_header and safe_name.lower().endswith(".wav"):
        return _ranged_file_response(path, media_type, range_header)
    return FileResponse(str(path), media_type=media_type, filename=safe_name)


def _ranged_file_response(path: Path, media_type: str, range_header: str) -> Response:
    size = path.stat().st_size
    try:
        units, rng = range_header.split("=", 1)
        if units.strip().lower() != "bytes":
            raise ValueError("unsupported unit")
        start_s, end_s = (rng.split("-", 1) + [""])[:2]
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else size - 1
    except (ValueError, IndexError):
        return FileResponse(str(path), media_type=media_type, filename=path.name)
    end = min(end, size - 1)
    if start > end or start >= size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    length = end - start + 1
    with path.open("rb") as f:
        f.seek(start)
        data = f.read(length)
    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return Response(content=data, status_code=206, media_type=media_type, headers=headers)

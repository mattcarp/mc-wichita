"""Guess likely aircraft for airband activity using receive-only ADS-B context (not a match)."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import wichita_adsb_live as wad
import wichita_adsb_tracks as wat
from wichita_airband_channel import nearest_lmml_channel_mhz, resolve_channel_label, lmml_voice_channels_vhf

LMML_LAT = 35.8575
LMML_LON = 14.4775
M_PER_NM = 1852.0

DEFAULT_RADIUS_NM = float(os.environ.get("WICHITA_AIRBAND_ADSB_RADIUS_NM", "40"))
DEFAULT_RECENCY_SEC = float(os.environ.get("WICHITA_AIRBAND_ADSB_RECENCY_SEC", "120"))
MAX_GUESSES = int(os.environ.get("WICHITA_AIRBAND_ADSB_MAX_GUESSES", "5"))


def _nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return (2 * r * math.asin(math.sqrt(a))) / M_PER_NM


def _fresh_enough(plane: Dict[str, Any], recency_sec: float) -> bool:
    last = plane.get("last_signal_s")
    if last is None:
        return False
    try:
        return float(last) <= recency_sec
    except (TypeError, ValueError):
        return False


def _rank_planes(
    planes: Sequence[Dict[str, Any]],
    *,
    radius_nm: float,
    recency_sec: float,
) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for p in planes:
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None or lon is None:
            continue
        if not _fresh_enough(p, recency_sec):
            continue
        d = _nm(float(lat), float(lon), LMML_LAT, LMML_LON)
        if d > radius_nm:
            continue
        ranked.append({**p, "distance_nm": round(d, 1)})
    ranked.sort(key=lambda x: (x.get("distance_nm", 99), x.get("last_signal_s") or 999))
    return ranked[:MAX_GUESSES]


def guess_payload(
    freq_mhz: Optional[float],
    *,
    event_time_utc: Optional[str] = None,
    planes: Optional[Sequence[Dict[str, Any]]] = None,
    radius_nm: float = DEFAULT_RADIUS_NM,
    recency_sec: float = DEFAULT_RECENCY_SEC,
) -> Dict[str, Any]:
    """Plain-language guess block for dashboard/API. Not a confirmed match."""
    label = resolve_channel_label(freq_mhz)
    lmml_ch = None
    if freq_mhz is not None:
        lmml_ch = nearest_lmml_channel_mhz(float(freq_mhz), lmml_voice_channels_vhf())
    if planes is None:
        if event_time_utc:
            track_rows = wat.get_track_store().snapshot_nearest(event_time_utc, max_delta_s=recency_sec)
            if track_rows:
                planes = track_rows
        if planes is None:
            snap = wad.live_adsb_snapshot()
            planes = snap.get("aircraft") or []
    ranked = _rank_planes(planes or [], radius_nm=radius_nm, recency_sec=recency_sec)
    if not ranked:
        sentence = "Likely aircraft on this channel: none near LMML in ADS-B (guess only, not a match)."
    else:
        bits = []
        for p in ranked:
            name = p.get("display_name") or p.get("callsign") or (p.get("hex") or "").upper()
            alt = p.get("altitude_ft")
            alt_s = f"{int(alt)} ft" if alt is not None else "alt unknown"
            bits.append(f"{name} ~{p.get('distance_nm')} nm, {alt_s}")
        sentence = "Likely aircraft on this channel (guess, not confirmed): " + "; ".join(bits) + "."
    return {
        "likely_aircraft_sentence": sentence,
        "likely_aircraft": ranked,
        "lmml_channel": lmml_ch,
        "lmml_channel_label": label,
        "freq_mhz": freq_mhz,
        "caveat": wat.OBSERVED_CAVEAT,
        "radius_nm": radius_nm,
        "recency_sec": recency_sec,
        "adsb_source": "tracks" if event_time_utc else "live",
        "event_time_utc": event_time_utc,
    }


def enrich_airband_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Add guess fields to a timeline / alert event dict."""
    meta = dict(ev.get("meta") or {})
    freq = meta.get("freq_mhz")
    if freq is None and isinstance(meta.get("channel"), str):
        pass
    t_utc = ev.get("time_utc")
    if t_utc is None and ev.get("t_utc") is not None:
        t_utc = datetime.fromtimestamp(float(ev["t_utc"]), tz=timezone.utc).isoformat()
    guess = guess_payload(freq, event_time_utc=t_utc)
    out = dict(ev)
    out["likely_aircraft_sentence"] = guess["likely_aircraft_sentence"]
    out["likely_aircraft"] = guess["likely_aircraft"]
    out["likely_aircraft_caveat"] = guess["caveat"]
    detail = (out.get("detail") or "").strip()
    if detail:
        out["detail"] = f"{detail} {guess['likely_aircraft_sentence']}"
    else:
        out["detail"] = guess["likely_aircraft_sentence"]
    if guess.get("lmml_channel_label"):
        title = out.get("title") or "Airband activity"
        if guess["lmml_channel_label"] not in title:
            out["title"] = f"{title} · {guess['lmml_channel_label']}"
    meta["likely_aircraft"] = guess["likely_aircraft"]
    meta["lmml_channel"] = guess.get("lmml_channel")
    out["meta"] = meta
    return out
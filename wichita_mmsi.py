"""In-app MMSI lookup: what the number itself encodes (ITU-R M.585) plus AIS static data we heard.

Everything here is derived from the MMSI digits, the bundled ITU MID table, or AIS messages our own
receiver decoded. No third-party lookups.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MID_TABLE = Path(__file__).resolve().parent / "data" / "itu_mid.json"
STATIC_FIELDS = ("shipname", "callsign", "imo", "shiptype", "destination", "draught",
                 "to_bow", "to_stern", "to_port", "to_starboard", "shipclass", "eni")


@lru_cache(maxsize=1)
def mid_table() -> Dict[str, str]:
    try:
        return json.loads(MID_TABLE.read_text(encoding="utf-8")).get("mids", {})
    except (OSError, ValueError):
        logger.warning("ITU MID table missing at %s", MID_TABLE)
        return {}


def _mid(code: str) -> Dict[str, Any]:
    country = mid_table().get(code)
    return {"mid": code, "mid_country": country}


def decode_mmsi(mmsi: Any) -> Dict[str, Any]:
    """Decode the station type and MID country from a 9-digit MMSI (ITU-R M.585)."""
    try:
        s = f"{int(mmsi):09d}"
    except (TypeError, ValueError):
        return {"valid": False, "kind": "invalid", "kind_label": "Not a valid MMSI"}
    if len(s) != 9:
        return {"mmsi": s, "valid": False, "kind": "invalid", "kind_label": "Not a 9-digit MMSI"}
    out: Dict[str, Any] = {"mmsi": s, "valid": True, "mid": None, "mid_country": None}
    if s.startswith("970"):
        out.update(kind="sart", kind_label="AIS-SART (search and rescue transmitter)")
    elif s.startswith("972"):
        out.update(kind="mob", kind_label="Man-overboard device")
    elif s.startswith("974"):
        out.update(kind="epirb", kind_label="EPIRB with AIS")
    elif s.startswith("111"):
        out.update(kind="sar_aircraft", kind_label="SAR aircraft", **_mid(s[3:6]))
    elif s.startswith("99"):
        sub = {"1": "Physical aid to navigation", "6": "Virtual aid to navigation"}.get(s[5], "Aid to navigation")
        out.update(kind="aton", kind_label=sub, **_mid(s[2:5]))
    elif s.startswith("98"):
        out.update(kind="craft", kind_label="Craft associated with a parent ship", **_mid(s[2:5]))
    elif s.startswith("00"):
        out.update(kind="coast_station", kind_label="Coast station", **_mid(s[2:5]))
    elif s.startswith("0"):
        out.update(kind="group", kind_label="Group of ships", **_mid(s[1:4]))
    elif s.startswith("8"):
        out.update(kind="handheld", kind_label="Handheld VHF (DSC/GNSS)", **_mid(s[1:4]))
    elif s[0] in "234567":
        out.update(kind="ship", kind_label="Ship station", **_mid(s[0:3]))
    else:
        out.update(kind="unknown", kind_label="Unallocated MMSI pattern")
    if out.get("mid") and not out.get("mid_country"):
        out["mid_country"] = "Unallocated MID"
    return out


def registry_file() -> Optional[Path]:
    raw = os.environ.get("WICHITA_AIS_REGISTRY_FILE", "").strip()
    if not raw:
        snaps = os.environ.get("WICHITA_AIS_SNAPSHOTS_DIR", "").strip()
        if not snaps:
            return None
        raw = str(Path(snaps).expanduser().parent / "ais_registry.json")
    return Path(raw).expanduser()


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    path = path if path is not None else registry_file()
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _clean(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip().strip("@").strip()
        return v or None
    if isinstance(v, (int, float)) and v == 0:
        return None
    return v


def update_registry(ships_raw, path: Optional[Path] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Merge AIS static fields we decoded into the persisted registry (last non-empty value wins)."""
    path = path if path is not None else registry_file()
    reg = load_registry(path)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    changed = False
    for raw in ships_raw or []:
        try:
            key = str(int(raw.get("mmsi") or 0))
        except (TypeError, ValueError):
            continue
        if key == "0":
            continue
        entry = reg.setdefault(key, {"first_seen_utc": stamp})
        entry["last_seen_utc"] = stamp
        if raw.get("country") and not entry.get("ais_country"):
            entry["ais_country"] = raw.get("country")
        for f in STATIC_FIELDS:
            v = _clean(raw.get(f))
            if v is not None and entry.get(f) != v:
                entry[f] = v
                changed = True
        changed = True
    if changed and path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(reg), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            logger.warning("AIS registry not saved: %s", exc)
    return reg


def lookup(mmsi: Any, registry: Optional[Dict[str, Any]] = None, shiptype_label=None) -> Dict[str, Any]:
    info = decode_mmsi(mmsi)
    reg = registry if registry is not None else load_registry()
    st = dict(reg.get(str(int(mmsi))) or {}) if info.get("valid") else {}
    bow, stern, port, stbd = (st.get(k) for k in ("to_bow", "to_stern", "to_port", "to_starboard"))
    if bow and stern:
        st["length_m"] = bow + stern
    if port and stbd:
        st["beam_m"] = port + stbd
    if shiptype_label and st.get("shiptype") is not None:
        st["shiptype_label"] = shiptype_label(st.get("shiptype"))
    info["static"] = st
    info["source"] = "MMSI digits (ITU-R M.585), ITU MID table, AIS static data decoded by our receiver"
    return info

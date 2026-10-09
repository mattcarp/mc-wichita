"""Plain-English copy for live AIS ships (no invented destinations)."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

# ITU-R M.1371 navigation status (0-15)
_NAV_STATUS: Dict[int, str] = {
    0: "under way",
    1: "at anchor",
    2: "not under command",
    3: "restricted manoeuvrability",
    4: "constrained by draught",
    5: "moored",
    6: "aground",
    7: "engaged in fishing",
    8: "under way sailing",
    15: "status not defined",
}

# Common Malta / regional UN/LOCODE prefixes (5-char); unknown codes stay raw.
_MALTA_LOCODE: Dict[str, str] = {
    "MTMLA": "Valletta",
    "MTSPB": "Marsaxlokk / Freeport",
    "MTMSX": "Msida",
    "MTMAR": "Marsaxlokk",
    "MTMGZ": "Mġarr (Gozo)",
    "MTCKW": "Ċirkewwa",
    "MTSLM": "Sliema",
    "MTMRS": "Marsamxett",
    "MTGOZ": "Gozo",
    "MTBUG": "Bugibba",
    "MTMST": "Marsaskala",
}

_SHIPTYPE_CATEGORY: Dict[str, str] = {
    "passenger": "passenger",
    "cargo": "cargo",
    "tanker": "tanker",
    "sailing": "sailing",
    "pleasure craft": "pleasure",
    "pilot": "pilot",
    "tug": "tug",
    "search and rescue": "sar",
    "port tender": "tender",
    "fishing": "fishing",
    "high-speed craft": "hsc",
    "other": "other",
    "not available": "other",
    "unknown type": "other",
}

# AIS type 40 = HSC
_EXTRA_SHIPTYPE: Dict[int, str] = {40: "high-speed craft", 41: "high-speed craft"}


def nav_status_label(code: Any) -> str:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "status unknown"
    if c in _NAV_STATUS:
        return _NAV_STATUS[c]
    if 9 <= c <= 14:
        return "reserved status"
    return "status unknown"


_PLAIN_DEST_ALIASES: Dict[str, str] = {
    "VALLETTA": "Valletta",
    "MARSAXLOKK": "Marsaxlokk",
    "MARSAMXETT": "Marsamxett",
    "SLIEMA": "Sliema",
    "GOZO": "Gozo",
    "POZZALLO": "Pozzallo",
    "MSIDA": "Msida",
    "BUGIBBA": "Bugibba",
    "CIRKEWWA": "Ċirkewwa",
    "MELLIEHA": "Mellieħa",
}


def decode_destination(raw: Optional[str]) -> Tuple[Optional[str], str, bool]:
    """Return (display_name_or_none, raw_trimmed, decoded_ok)."""
    if not raw:
        return None, "", True
    text = raw.strip()
    if not text:
        return None, "", True
    plain = re.sub(r"[^A-Za-z0-9]+", "", text).upper()
    if plain in _PLAIN_DEST_ALIASES:
        return _PLAIN_DEST_ALIASES[plain], text, True
    cleaned = re.sub(r"^[>\\s]+", "", text)
    cleaned = cleaned.replace(" ", "").upper()
    # LOCODE at start (2 letter country + 3 letter location)
    m = re.match(r"^([A-Z]{2}[A-Z0-9]{3})", cleaned)
    if m:
        code = m.group(1)
        if code in _MALTA_LOCODE:
            return _MALTA_LOCODE[code], text, True
        return None, text, False
    # Plain place names we recognise
    upper = text.upper()
    for key, name in _MALTA_LOCODE.items():
        if key[2:] in upper or name.upper() in upper:
            return name, text, True
    if "LOCAL WATERS" in upper:
        return "local waters (restricted)", text, True
    return None, text, False


def shiptype_phrase(shiptype_label: str, shiptype_code: Any = None) -> str:
    """Short type phrase for event sentences."""
    cat = shiptype_category(shiptype_label, shiptype_code)
    mapping = {
        "passenger": "passenger ferry",
        "pleasure": "pleasure craft",
        "sailing": "sailing yacht",
        "cargo": "cargo vessel",
        "tanker": "tanker",
        "pilot": "pilot boat",
        "tender": "port tender",
        "fishing": "fishing vessel",
        "hsc": "high-speed craft",
        "sar": "search and rescue vessel",
        "tug": "tug",
        "other": shiptype_label if shiptype_label not in ("not available", "unknown type") else "vessel",
    }
    return mapping.get(cat, shiptype_label or "vessel")


def first_heard_sentence(ship: Dict[str, Any]) -> str:
    name = ship.get("display_name") or ""
    mmsi = ship.get("mmsi")
    st = ship.get("shiptype_label")
    phrase = shiptype_phrase(st, ship.get("shiptype_code"))
    dest = ship.get("destination_display") or ship.get("destination_raw")
    unnamed = name.startswith("Unnamed") or name.startswith("An unnamed")
    if unnamed and mmsi:
        base = f"Unnamed MMSI {ship.get('mmsi_display') or f'{int(mmsi):09d}'} ({phrase}) heard for the first time today"
    else:
        base = f"{name} ({phrase}) heard for the first time today"
    if dest:
        base += f", heading for {dest}"
    return base + "."


def shiptype_category(shiptype_label: str, shiptype_code: Any = None) -> str:
    try:
        c = int(shiptype_code) if shiptype_code is not None else None
    except (TypeError, ValueError):
        c = None
    if c is not None and c in _EXTRA_SHIPTYPE:
        return _SHIPTYPE_CATEGORY.get(_EXTRA_SHIPTYPE[c], "other")
    return _SHIPTYPE_CATEGORY.get((shiptype_label or "").lower(), "other")


def compass_from_deg(deg: Optional[float]) -> str:
    if deg is None:
        return ""
    try:
        d = float(deg) % 360
    except (TypeError, ValueError):
        return ""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(round(d / 45)) % 8
    return dirs[idx]


def ship_length_m(raw: Dict[str, Any]) -> Optional[float]:
    bow = raw.get("to_bow")
    stern = raw.get("to_stern")
    try:
        if bow is not None and stern is not None:
            return float(bow) + float(stern)
    except (TypeError, ValueError):
        pass
    return None


def lead_sentence(
    *,
    nav_status: Any,
    speed_kn: Any,
    cog_deg: Any,
    destination_raw: Optional[str],
    destination_name: Optional[str],
    destination_decoded: bool,
    shiptype_label: str,
    near_label: Optional[str] = None,
) -> str:
    nav = nav_status_label(nav_status)
    try:
        spd = float(speed_kn) if speed_kn is not None else None
    except (TypeError, ValueError):
        spd = None
    dest_part = ""
    if destination_name:
        dest_part = f"toward {destination_name}"
    elif destination_raw:
        dest_part = f"toward {destination_raw.strip()}"

    if nav in ("moored", "at anchor") or (spd is not None and spd < 0.5):
        place = near_label or "harbour waters"
        if nav == "at anchor":
            return f"At anchor in {place}"
        return f"Moored in {place}"

    if spd is not None and spd >= 0.5:
        spd_r = round(spd, 1)
        comp = compass_from_deg(cog_deg)
        bits = [f"Under way at {spd_r} kn"]
        if comp:
            bits.append(f"heading {comp}")
        if dest_part:
            bits.append(dest_part)
        return ", ".join(bits)

    if nav == "under way sailing":
        return "Under way sailing" + (f", {dest_part}" if dest_part else "")

    if dest_part:
        return dest_part[0].upper() + dest_part[1:]
    return nav[0].upper() + nav[1:] if nav else "Movement unknown"


def enrich_ship_copy(ship: Dict[str, Any], raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raw = raw or {}
    dest_name, dest_raw, decoded = decode_destination(ship.get("destination") or raw.get("destination"))
    st_label = ship.get("shiptype_label") or "unknown type"
    cat = shiptype_category(st_label, ship.get("shiptype_code") or raw.get("shiptype"))
    nav = ship.get("nav_status") if ship.get("nav_status") is not None else raw.get("status")
    sentence = lead_sentence(
        nav_status=nav,
        speed_kn=ship.get("speed_kn"),
        cog_deg=ship.get("cog_deg"),
        destination_raw=dest_raw or ship.get("destination"),
        destination_name=dest_name,
        destination_decoded=decoded,
        shiptype_label=st_label,
        near_label="Grand Harbour",
    )
    out = dict(ship)
    out["nav_status"] = int(nav) if nav is not None else None
    out["nav_status_label"] = nav_status_label(nav)
    out["destination_raw"] = dest_raw or ship.get("destination")
    out["destination_display"] = dest_name
    out["destination_decoded"] = decoded
    out["shiptype_category"] = cat
    out["lead_sentence"] = sentence
    if raw:
        length = ship_length_m(raw)
        if length is not None:
            out["length_m"] = round(length, 1)
    return out


def freshness_bucket(last_signal_s: Optional[float]) -> str:
    if last_signal_s is None:
        return "earlier"
    if last_signal_s < 120:
        return "now"
    if last_signal_s < 600:
        return "recent"
    return "earlier"


def movement_counts(ships: List[Dict[str, Any]]) -> Dict[str, int]:
    """Disjoint moving vs moored/slow among vessels heard in the 'now' bucket."""
    now_ships = [s for s in ships if freshness_bucket(s.get("last_signal_s")) == "now"]
    moving = sum(1 for s in now_ships if (s.get("speed_kn") or 0) >= 0.5)
    moored = len(now_ships) - moving
    return {
        "now": len(now_ships),
        "moving": moving,
        "moored_or_slow": moored,
    }


def count_freshness(ships: List[Dict[str, Any]]) -> Dict[str, int]:
    now = recent = earlier = 0
    for s in ships:
        b = freshness_bucket(s.get("last_signal_s"))
        if b == "now":
            now += 1
        elif b == "recent":
            recent += 1
        else:
            earlier += 1
    return {"now": now, "recent": recent, "earlier": earlier, "today": len(ships)}


def type_breakdown_now(ships: List[Dict[str, Any]]) -> Dict[str, int]:
    type_counts: Dict[str, int] = {}
    for s in ships:
        if s.get("is_base_station"):
            continue
        if freshness_bucket(s.get("last_signal_s")) != "now":
            continue
        t = s.get("shiptype_label") or "vessels"
        type_counts[t] = type_counts.get(t, 0) + 1
    return type_counts


def harbour_summary(ships: List[Dict[str, Any]], online: bool, voice_not_monitored: bool) -> str:
    vessels = [s for s in ships if not s.get("is_base_station")]
    counts = count_freshness(vessels)
    move = movement_counts(vessels)
    moving = move["moving"]
    moored = move["moored_or_slow"]
    type_counts = type_breakdown_now(vessels)
    top_types = sorted(type_counts.items(), key=lambda x: (-x[1], x[0]))[:3]
    type_phrase = ", ".join(f"{n} {t}" for t, n in top_types) if top_types else "few vessels"
    lead = f"{counts['now']} nearby now ({type_phrase})"
    if moving:
        lead += f"; {moving} moving"
    if moored:
        lead += f", {moored} moored or slow"
    tail = "Receiver live" if online else "Receiver offline"
    if voice_not_monitored:
        tail += " · voice channels not monitored now (AIS on the SDR)"
    return f"{lead}. {tail}."

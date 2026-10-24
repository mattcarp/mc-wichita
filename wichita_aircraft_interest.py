"""Aircraft of interest: watch list, conditional rules, alerts, ADS-B enrichment."""

from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import wichita_ais_live as wal
import wichita_adsb_live as wad
from wichita_interest import (
    HEARD_IN_RECEPTION_S,
    REARM_SILENCE_S,
    _format_malta,
    _load_doc,
    _lock,
    _save_doc,
    list_flights,
)

logger = logging.getLogger(__name__)

EventFn = Callable[..., Any]

M_PER_NM = 1852.0
STATION_LAT = wal.RECEIVER_LAT
STATION_LON = wal.RECEIVER_LON
LMML_LAT = 35.8575
LMML_LON = 14.4775
LMML_EXCLUDE_RADIUS_NM = 5.0

LOITER_RADIUS_M = 1800.0
LOITER_MIN_SPEED_KTS = 45.0
LOITER_MAX_SPEED_KTS = 280.0

DEFAULT_AIRCRAFT_RULES: List[Dict[str, Any]] = [
    {
        "id": "close-low-default",
        "kind": "close_low",
        "enabled": True,
        "label": "Close and low",
        "max_range_nm": 10.0,
        "max_altitude_ft": 3000.0,
        "exclude_lmml_traffic": True,
    },
    {
        "id": "emergency-squawk",
        "kind": "emergency_squawk",
        "enabled": True,
        "label": "Emergency squawk 7500/7600/7700",
    },
    {
        "id": "loiter-near-station",
        "kind": "loiter",
        "enabled": True,
        "label": "Loitering / circling nearby",
        "max_range_nm": 25.0,
        "max_altitude_ft": 8000.0,
        "min_minutes": 12.0,
    },
]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return _haversine_m(lat1, lon1, lat2, lon2) / M_PER_NM


def list_aircraft_rules() -> List[Dict[str, Any]]:
    with _lock:
        doc = _load_doc()
        rules = doc.get("aircraft_rules")
        if not isinstance(rules, list) or not rules:
            return [dict(r) for r in DEFAULT_AIRCRAFT_RULES]
        return list(rules)


def save_aircraft_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    with _lock:
        doc = _load_doc()
        doc["aircraft_rules"] = rules
        _save_doc(doc)
    return list_aircraft_rules()


def _ensure_default_rules(doc: Dict[str, Any]) -> None:
    if not doc.get("aircraft_rules"):
        doc["aircraft_rules"] = [dict(r) for r in DEFAULT_AIRCRAFT_RULES]


def add_flight(
    *,
    hex_id: Optional[str] = None,
    callsign: Optional[str] = None,
    registration: Optional[str] = None,
    label: Optional[str] = None,
    note: Optional[str] = None,
    flight_id: Optional[str] = None,
) -> Dict[str, Any]:
    hx = (hex_id or "").strip().lower() or None
    cs = callsign.strip() if callsign else None
    reg = registration.strip() if registration else None
    if not hx and not cs and not reg:
        raise ValueError("Need ICAO hex, callsign, or registration")
    entry = {
        "id": flight_id or str(uuid.uuid4()),
        "hex": hx,
        "callsign": cs,
        "registration": reg,
        "label": label,
        "note": note,
        "added_utc": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        doc = _load_doc()
        _ensure_default_rules(doc)
        flights = doc.setdefault("flights", [])
        for f in flights:
            if hx and (f.get("hex") or "").lower() == hx:
                raise ValueError("ICAO hex already on the aircraft watch list")
        flights.append(entry)
        _save_doc(doc)
    return entry


def remove_flight(flight_id: str) -> bool:
    with _lock:
        doc = _load_doc()
        flights = doc.get("flights") or []
        new = [f for f in flights if f.get("id") != flight_id]
        if len(new) == len(flights):
            return False
        doc["flights"] = new
        _save_doc(doc)
    return True


def _norm_hex(q: str) -> Optional[str]:
    s = re.sub(r"[^0-9a-fA-F]", "", q)
    if len(s) == 6:
        return s.lower()
    return None


def _match_score(hay: str, needle: str) -> int:
    if not hay or not needle:
        return 0
    h, n = hay.lower(), needle.lower()
    if h == n:
        return 100
    if n in h:
        return 80
    return 0


def lookup_aircraft_candidates(query: str, planes: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    candidates: Dict[str, Dict[str, Any]] = {}
    hx_q = _norm_hex(q)

    def add(hex_id: str, source: str, score: int, **fields: Any) -> None:
        key = hex_id.lower()
        prev = candidates.get(key)
        row = {
            "hex": key,
            "hex_display": key.upper(),
            "sources": [source],
            "score": score,
            **fields,
        }
        if prev:
            row["sources"] = sorted(set(prev.get("sources", []) + [source]))
            row["score"] = max(prev.get("score", 0), score)
            for k, v in prev.items():
                if k not in row and v is not None:
                    row[k] = v
        if not row.get("display_name"):
            row["display_name"] = row.get("callsign") or row["hex_display"]
        candidates[key] = row

    if hx_q:
        add(hx_q, "icao_hex", 95)

    for p in planes or []:
        hx = (p.get("hex") or p.get("id") or "").lower()
        if not hx:
            continue
        sc = max(
            _match_score(hx, q),
            _match_score(p.get("callsign") or "", q),
            _match_score(p.get("registration") or "", q),
            _match_score(p.get("display_name") or "", q),
            95 if hx_q and hx == hx_q else 0,
        )
        if sc > 0:
            add(
                hx,
                "adsb_live",
                sc,
                callsign=p.get("callsign"),
                registration=p.get("registration"),
                type=p.get("type"),
                lat=p.get("lat"),
                lon=p.get("lon"),
                altitude_ft=p.get("altitude_ft"),
                last_heard_utc=p.get("last_heard_utc"),
                last_signal_s=p.get("last_signal_s"),
            )

    ranked = sorted(candidates.values(), key=lambda r: (-r.get("score", 0), r.get("hex", "")))
    return ranked[:12]


def _flight_matches_plane(flight: Dict[str, Any], plane: Dict[str, Any]) -> bool:
    hx = (flight.get("hex") or "").lower()
    ph = (plane.get("hex") or plane.get("id") or "").lower()
    if hx and ph and hx == ph:
        return True
    fcs = (flight.get("callsign") or "").strip().lower()
    pcs = (plane.get("callsign") or "").strip().lower()
    if fcs and pcs and fcs == pcs:
        return True
    fr = (flight.get("registration") or "").strip().lower()
    pr = (plane.get("registration") or "").strip().lower()
    if fr and pr and fr == pr:
        return True
    return False


def _rule_filters_plane(rule: Dict[str, Any], plane: Dict[str, Any]) -> bool:
    for key, field in (("hex", "hex"), ("callsign", "callsign"), ("registration", "registration")):
        want = rule.get(key)
        if not want:
            continue
        got = (plane.get(field) or plane.get("id") if field == "hex" else plane.get(field)) or ""
        if str(want).lower() not in str(got).lower():
            return False
    return True


def _near_lmml(plane: Dict[str, Any]) -> bool:
    lat, lon = plane.get("lat"), plane.get("lon")
    if lat is None or lon is None:
        return False
    return distance_nm(float(lat), float(lon), LMML_LAT, LMML_LON) <= LMML_EXCLUDE_RADIUS_NM


def _plane_in_reception(plane: Optional[Dict[str, Any]]) -> bool:
    if not plane:
        return False
    last = plane.get("last_signal_s")
    if last is None:
        return False
    try:
        return float(last) < HEARD_IN_RECEPTION_S
    except (TypeError, ValueError):
        return False


def _evaluate_close_low(rule: Dict[str, Any], plane: Dict[str, Any], range_nm: float) -> bool:
    if not _rule_filters_plane(rule, plane):
        return False
    max_r = float(rule.get("max_range_nm", 10))
    max_alt = float(rule.get("max_altitude_ft", 3000))
    alt = plane.get("altitude_ft")
    if alt is None:
        return False
    try:
        alt_f = float(alt)
    except (TypeError, ValueError):
        return False
    if range_nm > max_r or alt_f > max_alt:
        return False
    if rule.get("exclude_lmml_traffic") and _near_lmml(plane):
        return False
    return True


def _evaluate_emergency(rule: Dict[str, Any], plane: Dict[str, Any]) -> bool:
    if not rule.get("enabled", True):
        return False
    if not _rule_filters_plane(rule, plane):
        return False
    return bool(plane.get("is_emergency"))


def matching_rules(plane: Dict[str, Any], range_nm: float, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        kind = rule.get("kind")
        if kind == "close_low" and _evaluate_close_low(rule, plane, range_nm):
            hits.append(rule)
        elif kind == "emergency_squawk" and _evaluate_emergency(rule, plane):
            hits.append(rule)
    return hits


def _interest_label(flight: Dict[str, Any], plane: Optional[Dict[str, Any]]) -> str:
    if flight.get("label"):
        return str(flight["label"])
    if plane and plane.get("display_name"):
        return str(plane["display_name"])
    if flight.get("callsign"):
        return str(flight["callsign"])
    if flight.get("hex"):
        return str(flight["hex"]).upper()
    return "Aircraft of interest"


def _finalize_interest_plane(flight: Dict[str, Any], plane: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(plane)
    out["is_aircraft_of_interest"] = True
    out["interest_id"] = flight.get("id")
    out["interest_label"] = _interest_label(flight, plane)
    if flight.get("label"):
        out["display_name"] = flight["label"]
    heard = out.get("last_heard_utc")
    if heard:
        malta = _format_malta(heard)
        out["interest_last_malta"] = malta
        out["interest_heard_label"] = f"Last seen {malta}"
    else:
        out["interest_heard_label"] = "Not in feed right now"
    return out


def interest_aircraft_for_bundle(planes: List[Dict[str, Any]], now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    flights = list_flights()
    if not flights:
        return []
    now = now or datetime.now(timezone.utc)
    live_by_hex: Dict[str, Dict[str, Any]] = {}
    for p in planes:
        hx = (p.get("hex") or p.get("id") or "").lower()
        if hx:
            live_by_hex[hx] = p
    out: List[Dict[str, Any]] = []
    for flight in flights:
        live = None
        for p in planes:
            if _flight_matches_plane(flight, p):
                live = p
                break
        if live:
            out.append(_finalize_interest_plane(flight, dict(live)))
        else:
            stub = {
                "id": (flight.get("hex") or flight.get("id") or "unknown").lower(),
                "hex": flight.get("hex"),
                "callsign": flight.get("callsign"),
                "registration": flight.get("registration"),
                "display_name": _interest_label(flight, None),
                "lat": None,
                "lon": None,
                "altitude_ft": None,
                "last_signal_s": None,
                "last_heard_utc": None,
            }
            out.append(_finalize_interest_plane(flight, stub))
    return out


def enrich_adsb_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    planes = list(snap.get("aircraft") or [])
    rules = list_aircraft_rules()
    flights = list_flights()
    interest_rows = interest_aircraft_for_bundle(planes)
    interest_hexes = {
        (p.get("hex") or p.get("id") or "").lower()
        for p in interest_rows
        if p.get("hex") or p.get("id")
    }
    rule_alert_planes: List[Dict[str, Any]] = []

    for p in planes:
        lat, lon = p.get("lat"), p.get("lon")
        if lat is not None and lon is not None:
            p["range_nm"] = round(distance_nm(STATION_LAT, STATION_LON, float(lat), float(lon)), 2)
        else:
            p["range_nm"] = None
        matched = matching_rules(p, float(p["range_nm"] or 9999), rules)
        watch = any(_flight_matches_plane(f, p) for f in flights)
        if watch:
            p["is_aircraft_of_interest"] = True
            for f in flights:
                if _flight_matches_plane(f, p):
                    p["interest_id"] = f.get("id")
                    p["interest_label"] = _interest_label(f, p)
                    break
        if matched:
            p["interest_rule_matches"] = [r.get("id") for r in matched]
            p["interest_alert"] = True
            p["interest_alert_label"] = matched[0].get("label") or matched[0].get("id")
            rule_alert_planes.append(p)
        elif watch:
            p["interest_alert"] = bool(p.get("is_emergency"))

    def sort_key(p: Dict[str, Any]) -> Tuple:
        return (
            not p.get("is_aircraft_of_interest"),
            not p.get("interest_alert"),
            not p.get("is_emergency"),
            p.get("freshness") == "now" if p.get("freshness") else True,
            (p.get("callsign") or p.get("hex") or "").upper(),
        )

    merged = sorted(planes, key=sort_key)
    out = dict(snap)
    out["aircraft"] = merged
    out["interest_aircraft"] = interest_rows
    out["aircraft_of_interest_count"] = len(flights)
    out["aircraft_rule_alert_count"] = len(rule_alert_planes)
    out["aircraft_rules"] = rules
    out["station"] = {"lat": STATION_LAT, "lon": STATION_LON, "label": "Valletta station (50 Archbishop St)"}
    return out


class AircraftInterestEngine:
    """Watch-list heard alerts, conditional rules, and loiter detection."""

    def __init__(self, emit: EventFn) -> None:
        self._emit = emit
        self._in_reception: Dict[str, bool] = {}
        self._armed: Dict[str, bool] = {}
        self._last_fresh_mono: Dict[str, float] = {}
        self._rule_armed: Dict[Tuple[str, str], bool] = {}
        self._loiter_anchor: Dict[str, Tuple[float, float, float]] = {}
        self._loiter_logged: Set[str] = set()
        self._bootstrapped = False

    def ingest_planes(self, planes: List[Dict[str, Any]]) -> None:
        flights = list_flights()
        rules = list_aircraft_rules()
        now_mono = time.monotonic()
        by_hex: Dict[str, Dict[str, Any]] = {}
        for p in planes:
            hx = (p.get("hex") or p.get("id") or "").lower()
            if hx:
                by_hex[hx] = p

        if not self._bootstrapped:
            for flight in flights:
                key = self._flight_key(flight)
                in_rx = self._flight_in_reception(flight, by_hex)
                self._in_reception[key] = in_rx
                self._armed[key] = not in_rx
                if in_rx:
                    self._last_fresh_mono[key] = now_mono
            self._bootstrapped = True

        for flight in flights:
            key = self._flight_key(flight)
            plane = self._plane_for_flight(flight, by_hex)
            in_rx = self._flight_in_reception(flight, by_hex)
            was = self._in_reception.get(key, False)
            if in_rx:
                self._last_fresh_mono[key] = now_mono
                if not was and self._armed.get(key, True):
                    self._raise_watch_heard(flight, plane)
                    self._armed[key] = False
                self._in_reception[key] = True
            else:
                self._in_reception[key] = False
                if self._armed.get(key, True) is False:
                    last = self._last_fresh_mono.get(key, now_mono)
                    if now_mono - last >= REARM_SILENCE_S:
                        self._armed[key] = True

        for p in planes:
            hx = (p.get("hex") or p.get("id") or "").lower()
            if not hx:
                continue
            lat, lon = p.get("lat"), p.get("lon")
            range_nm = (
                distance_nm(STATION_LAT, STATION_LON, float(lat), float(lon))
                if lat is not None and lon is not None
                else 9999.0
            )
            for rule in matching_rules(p, range_nm, rules):
                if rule.get("kind") == "loiter":
                    continue
                rk = (str(rule.get("id")), hx)
                if self._rule_armed.get(rk, True):
                    self._raise_rule_alert(rule, p, range_nm)
                    self._rule_armed[rk] = False
            if not _plane_in_reception(p):
                for rule in rules:
                    if rule.get("kind") != "loiter":
                        self._rule_armed[(str(rule.get("id")), hx)] = True

            self._ingest_loiter(p, hx, range_nm, rules, now_mono)

    def _ingest_loiter(
        self,
        plane: Dict[str, Any],
        hx: str,
        range_nm: float,
        rules: List[Dict[str, Any]],
        now_mono: float,
    ) -> None:
        loiter_rules = [r for r in rules if r.get("kind") == "loiter" and r.get("enabled", True)]
        if not loiter_rules:
            return
        rule = loiter_rules[0]
        max_r = float(rule.get("max_range_nm", 25))
        max_alt = float(rule.get("max_altitude_ft", 8000))
        min_min = float(rule.get("min_minutes", 12))
        lat, lon = plane.get("lat"), plane.get("lon")
        if lat is None or lon is None or range_nm > max_r:
            self._loiter_anchor.pop(hx, None)
            return
        alt = plane.get("altitude_ft")
        try:
            alt_f = float(alt) if alt is not None else None
        except (TypeError, ValueError):
            alt_f = None
        if alt_f is None or alt_f > max_alt:
            self._loiter_anchor.pop(hx, None)
            return
        spd = plane.get("speed_kts")
        try:
            spd_f = float(spd) if spd is not None else 0.0
        except (TypeError, ValueError):
            spd_f = 0.0
        if spd_f < LOITER_MIN_SPEED_KTS or spd_f > LOITER_MAX_SPEED_KTS:
            self._loiter_anchor.pop(hx, None)
            return
        if not _plane_in_reception(plane):
            return
        poll = float(os.environ.get("WICHITA_EVENTS_POLL_SEC", "5"))
        anchor = self._loiter_anchor.get(hx)
        if anchor is None:
            self._loiter_anchor[hx] = (float(lat), float(lon), poll)
            return
        alat, alon, accum = anchor
        dist = _haversine_m(alat, alon, float(lat), float(lon))
        if dist > LOITER_RADIUS_M:
            self._loiter_anchor[hx] = (float(lat), float(lon), poll)
            return
        accum += poll
        self._loiter_anchor[hx] = (alat, alon, accum)
        if accum >= min_min * 60 and hx not in self._loiter_logged:
            self._loiter_logged.add(hx)
            rk = (str(rule.get("id")), hx)
            if self._rule_armed.get(rk, True):
                self._raise_loiter(rule, plane, range_nm, min_min)
                self._rule_armed[rk] = False

    @staticmethod
    def _flight_key(flight: Dict[str, Any]) -> str:
        return str(flight.get("id") or flight.get("hex") or flight.get("callsign") or uuid.uuid4())

    @staticmethod
    def _plane_for_flight(flight: Dict[str, Any], by_hex: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        hx = (flight.get("hex") or "").lower()
        if hx and hx in by_hex:
            return by_hex[hx]
        for p in by_hex.values():
            if _flight_matches_plane(flight, p):
                return p
        return None

    def _flight_in_reception(self, flight: Dict[str, Any], by_hex: Dict[str, Dict[str, Any]]) -> bool:
        plane = self._plane_for_flight(flight, by_hex)
        return _plane_in_reception(plane)

    def _raise_watch_heard(self, flight: Dict[str, Any], plane: Optional[Dict[str, Any]]) -> None:
        label = _interest_label(flight, plane)
        title = label if label.isupper() else label.title()
        lat = plane.get("lat") if plane else None
        lon = plane.get("lon") if plane else None
        alt = plane.get("altitude_ft") if plane else None
        pos = f"{lat:.5f}, {lon:.5f}" if lat is not None and lon is not None else "position unknown"
        alt_txt = f"{int(float(alt)):,} ft" if alt is not None else "altitude unknown"
        heard = plane.get("last_heard_utc") if plane else None
        malta = _format_malta(heard)
        sentence = f"{title} on watch list — {pos}, {alt_txt}, last seen {malta}."
        self._emit(
            "aircraft_of_interest_seen",
            sentence,
            hex=(plane or {}).get("hex"),
            display_name=label,
            interest_id=flight.get("id"),
            lat=lat,
            lon=lon,
            altitude_ft=alt,
            last_heard_utc=heard,
        )

    def _raise_rule_alert(self, rule: Dict[str, Any], plane: Dict[str, Any], range_nm: float) -> None:
        name = plane.get("display_name") or (plane.get("hex") or "").upper()
        label = rule.get("label") or rule.get("id")
        alt = plane.get("altitude_ft")
        alt_txt = f"{int(float(alt)):,} ft" if alt is not None else "altitude unknown"
        sq = plane.get("squawk")
        extra = f", squawk {sq}" if sq else ""
        sentence = f"Rule “{label}”: {name} at {range_nm:.1f} nmi, {alt_txt}{extra}."
        self._emit(
            "aircraft_rule_alert",
            sentence,
            rule_id=rule.get("id"),
            hex=plane.get("hex"),
            display_name=name,
            range_nm=range_nm,
            altitude_ft=alt,
            squawk=sq,
        )

    def _raise_loiter(self, rule: Dict[str, Any], plane: Dict[str, Any], range_nm: float, minutes: float) -> None:
        name = plane.get("display_name") or (plane.get("hex") or "").upper()
        label = rule.get("label") or rule.get("id")
        sentence = f"Rule “{label}”: {name} loitering ~{int(minutes)} min within {range_nm:.1f} nmi."
        self._emit(
            "aircraft_loiter",
            sentence,
            rule_id=rule.get("id"),
            hex=plane.get("hex"),
            display_name=name,
            range_nm=range_nm,
        )


_engine: Optional[AircraftInterestEngine] = None


def get_aircraft_interest_engine(emit: EventFn) -> AircraftInterestEngine:
    global _engine
    if _engine is None:
        _engine = AircraftInterestEngine(emit)
    return _engine

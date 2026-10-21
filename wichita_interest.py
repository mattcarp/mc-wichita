"""Boats (and later flights) of interest — server-side list, lookup, alerts, dashboard enrichment."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

import wichita_ais_live as wal
import wichita_mmsi
from wichita_ais_copy import enrich_ship_copy, freshness_bucket
from wichita_ais_tracks import get_snapshot_store

logger = logging.getLogger(__name__)

MALTA_TZ = ZoneInfo("Europe/Malta")
SEED_FILE = Path(__file__).resolve().parent / "config" / "interests_seed.json"

HEARD_IN_RECEPTION_S = float(os.environ.get("WICHITA_INTEREST_HEARD_S", "900"))
REARM_SILENCE_S = float(os.environ.get("WICHITA_INTEREST_REARM_S", str(6 * 3600)))

EventFn = Callable[..., Any]


def interests_file() -> Path:
    raw = os.environ.get("WICHITA_INTERESTS_FILE", "~/wichita/interests.json").strip()
    p = Path(raw).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _empty_doc() -> Dict[str, Any]:
    return {"schema_version": 1, "boats": [], "flights": []}


def _load_doc() -> Dict[str, Any]:
    path = interests_file()
    if not path.is_file():
        if SEED_FILE.is_file():
            try:
                seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
                if isinstance(seed, dict):
                    path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
                    return seed
            except (OSError, json.JSONDecodeError):
                pass
        return _empty_doc()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty_doc()
        data.setdefault("schema_version", 1)
        data.setdefault("boats", [])
        data.setdefault("flights", [])
        return data
    except (OSError, json.JSONDecodeError):
        return _empty_doc()


def _save_doc(doc: Dict[str, Any]) -> None:
    path = interests_file()
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


_lock = threading.Lock()


def list_boats() -> List[Dict[str, Any]]:
    with _lock:
        return list(_load_doc().get("boats") or [])


def list_flights() -> List[Dict[str, Any]]:
    with _lock:
        return list(_load_doc().get("flights") or [])


def watched_mmsi_set() -> Set[int]:
    out: Set[int] = set()
    for b in list_boats():
        try:
            out.add(int(b["mmsi"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def add_boat(
    *,
    mmsi: int,
    label: Optional[str] = None,
    callsign: Optional[str] = None,
    imo: Optional[int] = None,
    note: Optional[str] = None,
    boat_id: Optional[str] = None,
) -> Dict[str, Any]:
    entry = {
        "id": boat_id or str(uuid.uuid4()),
        "mmsi": int(mmsi),
        "label": label,
        "callsign": callsign,
        "imo": imo,
        "note": note,
        "added_utc": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        doc = _load_doc()
        boats = doc.setdefault("boats", [])
        if any(int(b.get("mmsi") or 0) == int(mmsi) for b in boats):
            raise ValueError("MMSI already on the boats-of-interest list")
        boats.append(entry)
        _save_doc(doc)
    return entry


def remove_boat(boat_id: str) -> bool:
    with _lock:
        doc = _load_doc()
        boats = doc.get("boats") or []
        new = [b for b in boats if b.get("id") != boat_id]
        if len(new) == len(boats):
            return False
        doc["boats"] = new
        _save_doc(doc)
    return True


def _digits_only(query: str) -> Optional[int]:
    digits = re.sub(r"\D", "", query)
    if len(digits) == 9:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def _roster_raw_by_mmsi(mmsi: int) -> Optional[Dict[str, Any]]:
    path = wal.roster_file()
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = (data.get("ships") or {}).get(str(mmsi))
        if entry:
            return dict(entry.get("raw") or {})
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return None


def _match_score(hay: str, needle: str) -> int:
    h = hay.lower()
    n = needle.lower()
    if h == n:
        return 100
    if n in h:
        return 80
    return 0


def lookup_boat_candidates(query: str, live_ships: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Resolve user input to candidate vessels (our feed + registry first)."""
    q = (query or "").strip()
    if not q:
        return []
    candidates: Dict[int, Dict[str, Any]] = {}
    mmsi_from_q = _digits_only(q)

    def add_candidate(mmsi: int, source: str, **fields: Any) -> None:
        key = int(mmsi)
        prev = candidates.get(key)
        score = fields.pop("score", 50)
        row = {
            "mmsi": key,
            "mmsi_display": f"{key:09d}",
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
        candidates[key] = row

    if mmsi_from_q is not None:
        add_candidate(mmsi_from_q, "mmsi", score=90)
        info = wichita_mmsi.lookup(mmsi_from_q, None, wal.shiptype_label)
        st = info.get("static") or {}
        if st.get("shipname"):
            add_candidate(mmsi_from_q, "registry", shipname=st["shipname"], score=92)
        if st.get("callsign"):
            add_candidate(mmsi_from_q, "registry", callsign=st["callsign"], score=92)
        payload, err = wal.fetch_ais_json(f"/api/ship.json?mmsi={mmsi_from_q}")
        if payload and not err:
            norm = wal.normalize_ship(payload, datetime.now(timezone.utc))
            add_candidate(
                mmsi_from_q,
                "our_receiver",
                shipname=norm.get("shipname"),
                display_name=norm.get("display_name"),
                callsign=norm.get("callsign"),
                imo=norm.get("imo"),
                lat=norm.get("lat"),
                lon=norm.get("lon"),
                last_heard_utc=norm.get("last_heard_utc"),
                score=95,
            )
        raw = _roster_raw_by_mmsi(mmsi_from_q)
        if raw:
            add_candidate(
                mmsi_from_q,
                "roster",
                shipname=raw.get("shipname"),
                callsign=raw.get("callsign"),
                score=88,
            )

    reg = wichita_mmsi.load_registry()
    for key, st in reg.items():
        try:
            mmsi = int(key)
        except ValueError:
            continue
        name = st.get("shipname") or ""
        cs = st.get("callsign") or ""
        sc = max(_match_score(name, q), _match_score(cs, q))
        if sc > 0:
            add_candidate(
                mmsi,
                "registry",
                shipname=name or None,
                callsign=cs or None,
                imo=st.get("imo"),
                score=sc,
            )

    for s in live_ships or []:
        if s.get("is_base_station"):
            continue
        try:
            mmsi = int(s["mmsi"])
        except (KeyError, TypeError, ValueError):
            continue
        sc = max(
            _match_score(s.get("display_name") or "", q),
            _match_score(s.get("shipname") or "", q),
            _match_score(s.get("callsign") or "", q),
            _match_score(str(mmsi), q),
        )
        if sc > 0 or (mmsi_from_q is not None and mmsi == mmsi_from_q):
            add_candidate(
                mmsi,
                "our_receiver",
                shipname=s.get("shipname"),
                display_name=s.get("display_name"),
                callsign=s.get("callsign"),
                imo=s.get("imo"),
                lat=s.get("lat"),
                lon=s.get("lon"),
                last_heard_utc=s.get("last_heard_utc"),
                score=max(sc, 70),
            )

    ranked = sorted(candidates.values(), key=lambda r: (-r.get("score", 0), r.get("mmsi", 0)))
    for row in ranked:
        if not row.get("display_name"):
            row["display_name"] = row.get("shipname") or f"MMSI {row['mmsi_display']}"
    return ranked[:12]


def _format_malta(ts_utc: Optional[str]) -> str:
    if not ts_utc:
        return "—"
    try:
        dt = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        return dt.astimezone(MALTA_TZ).strftime("%Y-%m-%d %H:%M %Z")
    except (TypeError, ValueError):
        return ts_utc


def _interest_label(boat: Dict[str, Any], ship: Optional[Dict[str, Any]]) -> str:
    if boat.get("label"):
        return str(boat["label"])
    if ship and ship.get("display_name"):
        return str(ship["display_name"])
    return f"MMSI {int(boat['mmsi']):09d}"


def _finalize_interest_vessel(boat: Dict[str, Any], ship: Dict[str, Any]) -> Dict[str, Any]:
    ship["is_boat_of_interest"] = True
    ship["interest_id"] = boat.get("id")
    ship["interest_label"] = _interest_label(boat, ship)
    if boat.get("label"):
        ship["display_name"] = boat["label"]
    ship = enrich_ship_copy(ship)
    heard_utc = ship.get("last_heard_utc")
    if heard_utc:
        ship["interest_last_malta"] = _format_malta(heard_utc)
        ship["interest_heard_label"] = f"Last heard {ship['interest_last_malta']}"
    else:
        ship.pop("interest_last_malta", None)
        ship["lead_sentence"] = "Not heard yet on our receiver."
        ship["freshness_label"] = "Not heard yet"
        ship["interest_heard_label"] = "Not heard yet"
    return ship


def _vessel_from_interest(
    boat: Dict[str, Any],
    live_by_mmsi: Dict[int, Dict[str, Any]],
    now: datetime,
) -> Dict[str, Any]:
    mmsi = int(boat["mmsi"])
    live = live_by_mmsi.get(mmsi)
    if live:
        out = dict(live)
        if boat.get("label"):
            out["display_name"] = boat["label"]
        return _finalize_interest_vessel(boat, out)

    raw = _roster_raw_by_mmsi(mmsi)
    if raw:
        ship = wal.normalize_ship(raw, now)
        ship["last_signal_s"] = max(ship.get("last_signal_s") or 0, REARM_SILENCE_S + 1)
        ship["freshness"] = "earlier"
        ship["freshness_label"] = "Earlier"
    else:
        reg = wichita_mmsi.load_registry().get(str(mmsi)) or {}
        name = boat.get("label") or reg.get("shipname")
        ship = {
            "mmsi": mmsi,
            "mmsi_display": f"{mmsi:09d}",
            "display_name": name or f"MMSI {mmsi:09d}",
            "shipname": reg.get("shipname"),
            "callsign": boat.get("callsign") or reg.get("callsign"),
            "imo": boat.get("imo") or reg.get("imo"),
            "lat": None,
            "lon": None,
            "speed_kn": None,
            "speed_known": False,
            "last_signal_s": None,
            "last_heard_utc": reg.get("last_seen_utc"),
            "freshness": "earlier",
            "freshness_label": "Not heard recently",
            "shiptype_label": wal.shiptype_label(reg.get("shiptype")) if reg.get("shiptype") else "vessel",
            "shiptype_category": "other",
            "is_base_station": False,
        }

    last = get_snapshot_store().last_known_vessel(mmsi)
    if last:
        ts_utc, snap = last
        if ship.get("lat") is None and snap.get("lat") is not None:
            ship["lat"] = snap["lat"]
            ship["lon"] = snap["lon"]
            ship["speed_kn"] = snap.get("speed_kn")
            ship["speed_known"] = snap.get("speed_kn") is not None
        if not ship.get("last_heard_utc"):
            ship["last_heard_utc"] = ts_utc
        try:
            heard = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
            ship["last_signal_s"] = max(0.0, (now - heard.astimezone(timezone.utc)).total_seconds())
            ship["freshness"] = freshness_bucket(ship.get("last_signal_s"))
            ship["freshness_label"] = {"now": "Now", "recent": "Recent", "earlier": "Earlier"}.get(
                ship["freshness"], "Earlier"
            )
        except (TypeError, ValueError):
            pass

    return _finalize_interest_vessel(boat, ship)


def interest_vessels_for_bundle(vessels: List[Dict[str, Any]], now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    boats = list_boats()
    if not boats:
        return []
    now = now or datetime.now(timezone.utc)
    live_by_mmsi = {int(s["mmsi"]): s for s in vessels if s.get("mmsi") is not None}
    return [_vessel_from_interest(b, live_by_mmsi, now) for b in boats]


class BoatInterestEngine:
    """Fire debounced 'heard' alerts when a boat of interest enters our AIS reception."""

    def __init__(self, emit: EventFn) -> None:
        self._emit = emit
        self._in_reception: Dict[int, bool] = {}
        self._armed: Dict[int, bool] = {}
        self._last_fresh_mono: Dict[int, float] = {}
        self._bootstrapped = False

    def ingest_ships(self, ships: List[Dict[str, Any]]) -> None:
        watched = list_boats()
        if not watched:
            return
        by_mmsi = {int(s["mmsi"]): s for s in ships if s.get("mmsi") is not None}
        now_mono = time.monotonic()

        if not self._bootstrapped:
            for boat in watched:
                mmsi = int(boat["mmsi"])
                in_rx = self._currently_in_reception(by_mmsi.get(mmsi))
                self._in_reception[mmsi] = in_rx
                self._armed[mmsi] = not in_rx
                if in_rx:
                    self._last_fresh_mono[mmsi] = now_mono
            self._bootstrapped = True

        for boat in watched:
            mmsi = int(boat["mmsi"])
            ship = by_mmsi.get(mmsi)
            in_rx = self._currently_in_reception(ship)
            was = self._in_reception.get(mmsi, False)

            if in_rx:
                self._last_fresh_mono[mmsi] = now_mono
                if not was and self._armed.get(mmsi, True):
                    self._raise_heard(boat, ship)
                    self._armed[mmsi] = False
                self._in_reception[mmsi] = True
            else:
                self._in_reception[mmsi] = False
                if self._armed.get(mmsi, True) is False:
                    last = self._last_fresh_mono.get(mmsi, now_mono)
                    if now_mono - last >= REARM_SILENCE_S:
                        self._armed[mmsi] = True

    @staticmethod
    def _currently_in_reception(ship: Optional[Dict[str, Any]]) -> bool:
        if not ship:
            return False
        last = ship.get("last_signal_s")
        if last is None:
            return False
        try:
            return float(last) < HEARD_IN_RECEPTION_S
        except (TypeError, ValueError):
            return False

    def _raise_heard(self, boat: Dict[str, Any], ship: Optional[Dict[str, Any]]) -> None:
        label = _interest_label(boat, ship)
        title = label if label.isupper() else label.title()
        lat = ship.get("lat") if ship else None
        lon = ship.get("lon") if ship else None
        spd = ship.get("speed_kn") if ship else None
        heard = ship.get("last_heard_utc") if ship else None
        malta = _format_malta(heard)
        pos = f"{lat:.5f}, {lon:.5f}" if lat is not None and lon is not None else "position unknown"
        spd_txt = f"{float(spd):.1f} kn" if spd is not None and ship.get("speed_known", True) else "speed unknown"
        sentence = f"{title} heard — {pos}, {spd_txt}, last heard {malta}."
        self._emit(
            "boat_of_interest_heard",
            sentence,
            mmsi=int(boat["mmsi"]),
            display_name=label,
            interest_id=boat.get("id"),
            lat=lat,
            lon=lon,
            speed_kn=spd,
            last_heard_utc=heard,
            last_heard_malta=malta,
        )
        try:
            from wichita_interest_notify import notify_boat_of_interest_heard

            notify_boat_of_interest_heard(title, pos, spd_txt, malta)
        except Exception as exc:
            logger.debug("interest notify skipped: %s", exc)


_engine: Optional[BoatInterestEngine] = None


def get_boat_interest_engine(emit: EventFn) -> BoatInterestEngine:
    global _engine
    if _engine is None:
        _engine = BoatInterestEngine(emit)
    return _engine

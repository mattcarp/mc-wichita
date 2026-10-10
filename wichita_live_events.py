"""Persist live AIS timeline events to JSONL on disk."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from wichita_ais_copy import enrich_ship_copy, first_heard_sentence, freshness_bucket
from wichita_timeline import DEFAULT_HOURS, DEFAULT_LIMIT, paginate_events, prepare_timeline_events

logger = logging.getLogger(__name__)

SILENCE_SEC = 900
MIN_HEARD_BEFORE_QUIET_SEC = 600
POLL_SEC = float(os.environ.get("WICHITA_EVENTS_POLL_SEC", "5"))
HARBOUR_LAT = (35.875, 35.925)
HARBOUR_LON = (14.48, 14.55)


def events_dir() -> Path:
    raw = os.environ.get("WICHITA_EVENTS_DIR", "~/wichita/live/events").strip()
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _day_path(when: datetime) -> Path:
    return events_dir() / f"events-{when.strftime('%Y-%m-%d')}.jsonl"


def append_event(kind: str, sentence: str, **fields: Any) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    rec = {
        "ts_utc": now.isoformat(),
        "kind": kind,
        "sentence": sentence,
        **fields,
    }
    path = _day_path(now)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _in_harbour(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    return HARBOUR_LAT[0] <= lat <= HARBOUR_LAT[1] and HARBOUR_LON[0] <= lon <= HARBOUR_LON[1]


class LiveEventEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen_mmsi: Set[int] = set()
        self._last_online: Optional[bool] = None
        self._last_nav: Dict[int, int] = {}
        self._silent_logged: Set[int] = set()
        self._first_seen_monotonic: Dict[int, float] = {}
        self._heard_accum_s: Dict[int, float] = {}
        self._moving_harbour: Dict[int, bool] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="wichita-live-events", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        import wichita_ais_live as wal

        while not self._stop.is_set():
            try:
                bundle = wal.live_dashboard_bundle()
                self.ingest_snapshot(bundle)
            except Exception as exc:
                logger.warning("live events poll failed: %s", exc)
            self._stop.wait(POLL_SEC)

    def _should_log_quiet(self, mmsi: int, enriched: Dict[str, Any]) -> bool:
        if self._moving_harbour.get(mmsi):
            return True
        heard = self._heard_accum_s.get(mmsi, 0.0)
        if heard >= MIN_HEARD_BEFORE_QUIET_SEC:
            return True
        last = enriched.get("last_signal_s")
        if last is not None and last >= SILENCE_SEC + 300:
            return True
        return False

    def ingest_snapshot(self, bundle: Dict[str, Any]) -> None:
        online = bool(bundle.get("online"))
        ships = bundle.get("ships") or []
        now_mono = time.monotonic()
        with self._lock:
            if self._last_online is None:
                self._last_online = online
            elif online and not self._last_online:
                append_event("receiver_up", "AIS receiver came back online.")
            elif not online and self._last_online:
                append_event("receiver_down", "AIS receiver went offline.")
            self._last_online = online

            try:
                from wichita_watch_zones import get_watch_engine

                get_watch_engine().ingest_ships(ships)
            except Exception as exc:
                logger.debug("watch zones ingest skipped: %s", exc)

            for s in ships:
                if s.get("is_base_station"):
                    continue
                mmsi = int(s["mmsi"])
                enriched = enrich_ship_copy(s)
                name = enriched.get("display_name") or f"MMSI {mmsi:09d}"
                if mmsi not in self._first_seen_monotonic:
                    self._first_seen_monotonic[mmsi] = now_mono
                if freshness_bucket(enriched.get("last_signal_s")) != "earlier":
                    self._heard_accum_s[mmsi] = self._heard_accum_s.get(mmsi, 0.0) + POLL_SEC
                    self._silent_logged.discard(mmsi)
                spd = enriched.get("speed_kn") or 0
                if spd >= 0.5 and _in_harbour(enriched.get("lat"), enriched.get("lon")):
                    self._moving_harbour[mmsi] = True

                if mmsi not in self._seen_mmsi:
                    self._seen_mmsi.add(mmsi)
                    sentence = first_heard_sentence(enriched)
                    append_event(
                        "ship_first_heard",
                        sentence,
                        mmsi=mmsi,
                        display_name=name,
                        first_heard_utc=enriched.get("last_heard_utc"),
                    )
                nav = enriched.get("nav_status")
                if nav is not None:
                    prev = self._last_nav.get(mmsi)
                    if prev is not None and prev != nav:
                        append_event(
                            "ship_status_change",
                            f"{name} changed status to {enriched.get('nav_status_label')}.",
                            mmsi=mmsi,
                        )
                    self._last_nav[mmsi] = int(nav)

                if freshness_bucket(enriched.get("last_signal_s")) != "earlier":
                    continue
                if mmsi in self._silent_logged:
                    continue
                if enriched.get("last_signal_s", 0) < SILENCE_SEC:
                    continue
                if not self._should_log_quiet(mmsi, enriched):
                    continue
                self._silent_logged.add(mmsi)
                append_event(
                    "ship_silent",
                    f"{name} has gone quiet (no AIS for {int(enriched['last_signal_s'] // 60)} min).",
                    mmsi=mmsi,
                    display_name=name,
                )

    def read_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        out: List[Dict[str, Any]] = []
        root = events_dir()
        for path in sorted(root.glob("events-*.jsonl")):
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    ts = datetime.fromisoformat(rec["ts_utc"].replace("Z", "+00:00"))
                    if ts >= cutoff:
                        out.append(rec)
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
        out.sort(key=lambda r: r.get("ts_utc", ""), reverse=True)
        return out

    def events_page(
        self,
        *,
        hours: int = DEFAULT_HOURS,
        limit: int = DEFAULT_LIMIT,
        before: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw = self.read_events(hours=hours)
        prepared = prepare_timeline_events(raw)
        page = paginate_events(prepared, limit=limit, before=before)
        page["activity_hourly"] = self.activity_hourly(hours=max(hours, 24))
        page["hours"] = hours
        return page

    def activity_hourly(self, hours: int = 24) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        counts = [0] * hours
        for ev in self.read_events(hours=hours):
            try:
                ts = datetime.fromisoformat(ev["ts_utc"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            age_h = (now - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
            if age_h < 0 or age_h >= hours:
                continue
            idx = hours - 1 - int(age_h)
            counts[idx] += 1
        return [
            {
                "hour_utc": (now - timedelta(hours=(hours - 1 - i))).strftime("%Y-%m-%dT%H:00"),
                "events": counts[i],
            }
            for i in range(hours)
        ]


_engine: Optional[LiveEventEngine] = None


def get_engine() -> LiveEventEngine:
    global _engine
    if _engine is None:
        _engine = LiveEventEngine()
    return _engine

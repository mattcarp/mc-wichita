"""Persist live AIS timeline events to JSONL on disk."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from wichita_ais_copy import enrich_ship_copy, freshness_bucket

logger = logging.getLogger(__name__)

SILENCE_SEC = 900
POLL_SEC = float(os.environ.get("WICHITA_EVENTS_POLL_SEC", "5"))


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


class LiveEventEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen_mmsi: Set[int] = set()
        self._last_online: Optional[bool] = None
        self._last_nav: Dict[int, int] = {}
        self._silent_logged: Set[int] = set()
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

    def ingest_snapshot(self, bundle: Dict[str, Any]) -> None:
        online = bool(bundle.get("online"))
        ships = bundle.get("ships") or []
        with self._lock:
            if self._last_online is None:
                self._last_online = online
            elif online and not self._last_online:
                append_event("receiver_up", "AIS receiver came back online.")
            elif not online and self._last_online:
                append_event("receiver_down", "AIS receiver went offline.")
            self._last_online = online

            for s in ships:
                if s.get("is_base_station"):
                    continue
                mmsi = int(s["mmsi"])
                enriched = enrich_ship_copy(s)
                name = enriched.get("display_name") or f"MMSI {mmsi:09d}"
                st = enriched.get("shiptype_label")
                if mmsi not in self._seen_mmsi:
                    self._seen_mmsi.add(mmsi)
                    dest = enriched.get("destination_display") or enriched.get("destination_raw")
                    bits = [name]
                    if st and st != "not available":
                        bits.append(f"({st})")
                    if dest:
                        bits.append(f"heading for {dest}")
                    sentence = f"{name} heard for the first time today" + (
                        f", {' '.join(bits[1:])}" if len(bits) > 1 else ""
                    )
                    append_event(
                        "ship_first_heard",
                        sentence + ".",
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
                    self._silent_logged.discard(mmsi)
                elif mmsi not in self._silent_logged and enriched.get("last_signal_s", 0) >= SILENCE_SEC:
                    self._silent_logged.add(mmsi)
                    append_event(
                        "ship_silent",
                        f"{name} has gone quiet (no AIS for {int(enriched['last_signal_s'] // 60)} min).",
                        mmsi=mmsi,
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

    def activity_hourly(self, hours: int = 24) -> List[Dict[str, Any]]:
        events = self.read_events(hours=hours)
        buckets: Dict[str, int] = defaultdict(int)
        for ev in events:
            if ev.get("kind") != "ship_first_heard":
                continue
            try:
                ts = datetime.fromisoformat(ev["ts_utc"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            key = ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
            buckets[key] += 1
        return [{"hour_utc": k, "new_ships": v} for k, v in sorted(buckets.items())]


_engine: Optional[LiveEventEngine] = None


def get_engine() -> LiveEventEngine:
    global _engine
    if _engine is None:
        _engine = LiveEventEngine()
    return _engine

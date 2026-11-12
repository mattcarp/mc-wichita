"""MMSI identity: invalid digits, impossible-speed splits, advisory-only alerts."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import wichita_mmsi
from wichita_track_signal import implied_speed_kn

IMPOSSIBLE_SPEED_KN = float(os.environ.get("WICHITA_AIS_IMPOSSIBLE_SPEED_KN", "75"))
IMPOSSIBLE_MIN_DT_SEC = float(os.environ.get("WICHITA_AIS_IMPOSSIBLE_MIN_DT_SEC", "30"))
JITTER_MARGIN_KN = float(os.environ.get("WICHITA_AIS_SPEED_JITTER_KN", "5"))

DEFAULT_MMSI_BLOCKLIST = frozenset(
    {
        0,
        111111111,
        123456789,
        999999999,
        200000000,
    }
)

ADVISORY_INVALID = "invalid_mmsi"
ADVISORY_SPOOF = "possible_shared_or_spoofed_mmsi"

ADVISORY_WO_SPOOF = (
    "Advisory only: this MMSI appeared at two positions faster than a plausible vessel "
    "could move — it may be shared, duplicated, or spoofed."
)
ADVISORY_WO_INVALID = "Advisory only: this MMSI looks invalid or non-standard for AIS."


def _format_mmsi(mmsi: Any) -> str:
    try:
        return f"{int(mmsi):09d}"
    except (TypeError, ValueError):
        return str(mmsi)


def invalid_mmsi_reasons(mmsi: Any) -> List[str]:
    reasons: List[str] = []
    raw = str(mmsi).strip()
    try:
        n = int(mmsi)
        disp = f"{n:09d}"
    except (TypeError, ValueError):
        return ["Not a numeric MMSI"]
    if len(disp) != 9:
        reasons.append("MMSI is not 9 digits")
    if n in DEFAULT_MMSI_BLOCKLIST:
        reasons.append("Known default or test MMSI pattern")
    if len(set(disp)) == 1 and disp[0] not in ("0",):
        reasons.append("Repeated-digit MMSI pattern")
    decoded = wichita_mmsi.decode_mmsi(mmsi)
    if not decoded.get("valid"):
        reasons.append(decoded.get("kind_label") or "Invalid MMSI encoding")
    elif decoded.get("mid_country") == "Unallocated MID":
        reasons.append("ITU MID not allocated")
    elif decoded.get("kind") == "unknown":
        reasons.append("Unallocated MMSI pattern")
    return reasons


def mmsi_advisory_record(
    *,
    kind: str,
    mmsi: int,
    detail: str,
    display_name: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "created_utc": now.isoformat(),
        "title": "Possible shared or spoofed MMSI" if kind == ADVISORY_SPOOF else "Invalid or non-standard MMSI",
        "detail": detail,
        "mmsi": mmsi,
        "mmsi_display": _format_mmsi(mmsi),
        "display_name": display_name,
        "severity": "advisory",
        "source": "wichita_ais_identity",
        **(extra or {}),
    }


def persist_advisory_alert(advisory: Dict[str, Any]) -> None:
    """Optional persistence to the human review queue (advisory wording, not accusation)."""
    try:
        import alert_store

        alert_store.append_alert_record(
            {
                "id": advisory["id"],
                "created_at": advisory["created_utc"],
                "title": advisory["title"],
                "description": advisory["detail"],
                "signal_type": "ais",
                "severity": "info",
                "frequency_mhz": 161.975,
                "confidence": 0.5,
                "transcript": None,
                "language": None,
                "audio_url": None,
                "tags": ["advisory", "ais", advisory.get("kind") or "mmsi"],
                "metadata": {
                    "mmsi": advisory.get("mmsi"),
                    "mmsi_display": advisory.get("mmsi_display"),
                    "advisory_kind": advisory.get("kind"),
                },
                "source": "wichita_ais_identity",
                "review_status": "pending_review",
            }
        )
    except Exception:
        pass


class AisMmsiIdentityTracker:
    """Track MMSI position continuity; split track keys when jumps imply impossible speed."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: Dict[int, Dict[str, Any]] = {}
        self._segment: Dict[int, int] = {}
        self._advisories: List[Dict[str, Any]] = []
        self._logged: Set[str] = set()

    def ingest_vessel(
        self,
        ship: Dict[str, Any],
        *,
        now_epoch: float,
        persist_alerts: bool = True,
    ) -> Dict[str, Any]:
        if ship.get("is_base_station"):
            return ship
        try:
            mmsi = int(ship["mmsi"])
        except (KeyError, TypeError, ValueError):
            return ship
        lat, lon = ship.get("lat"), ship.get("lon")
        name = ship.get("display_name") or f"MMSI {_format_mmsi(mmsi)}"

        invalid = invalid_mmsi_reasons(mmsi)
        if invalid:
            key = f"invalid:{mmsi}"
            ship["mmsi_advisory"] = ADVISORY_WO_INVALID
            ship["mmsi_advisory_reasons"] = invalid
            if key not in self._logged:
                rec = mmsi_advisory_record(
                    kind=ADVISORY_INVALID,
                    mmsi=mmsi,
                    display_name=name,
                    detail=f"{ADVISORY_WO_INVALID} ({'; '.join(invalid)})",
                    extra={"reasons": invalid},
                )
                self._advisories.append(rec)
                self._logged.add(key)
                if persist_alerts:
                    persist_advisory_alert(rec)

        if lat is None or lon is None:
            seg = self._segment.get(mmsi, 0)
            ship["track_key"] = f"{mmsi}" if seg == 0 else f"{mmsi}#{seg}"
            return ship

        with self._lock:
            prev = self._last.get(mmsi)
            seg = self._segment.get(mmsi, 0)
            if prev is not None and prev.get("lat") is not None:
                spd = implied_speed_kn(
                    float(prev["lat"]),
                    float(prev["lon"]),
                    float(prev["epoch"]),
                    float(lat),
                    float(lon),
                    float(now_epoch),
                )
                dt = abs(float(now_epoch) - float(prev["epoch"]))
                limit = IMPOSSIBLE_SPEED_KN + JITTER_MARGIN_KN
                if spd is not None and dt >= IMPOSSIBLE_MIN_DT_SEC and spd > limit:
                    seg += 1
                    self._segment[mmsi] = seg
                    adv_key = f"spoof:{mmsi}:{seg}"
                    if adv_key not in self._logged:
                        detail = (
                            f"{ADVISORY_WO_SPOOF} MMSI {_format_mmsi(mmsi)} "
                            f"({name}): implied {spd:.0f} kn over {dt:.0f} s "
                            f"(threshold {limit:.0f} kn)."
                        )
                        rec = mmsi_advisory_record(
                            kind=ADVISORY_SPOOF,
                            mmsi=mmsi,
                            display_name=name,
                            detail=detail,
                            extra={"implied_speed_kn": round(spd, 1), "delta_s": round(dt, 1), "track_segment": seg},
                        )
                        self._advisories.append(rec)
                        self._logged.add(adv_key)
                        ship["mmsi_advisory"] = ADVISORY_WO_SPOOF
                        if persist_alerts:
                            persist_advisory_alert(rec)
            self._last[mmsi] = {"lat": lat, "lon": lon, "epoch": now_epoch, "segment": seg}

        ship["track_key"] = f"{mmsi}" if seg == 0 else f"{mmsi}#{seg}"
        ship["track_segment"] = seg
        return ship

    def ingest_vessels(self, vessels: List[Dict[str, Any]], *, now_epoch: float) -> List[Dict[str, Any]]:
        return [self.ingest_vessel(v, now_epoch=now_epoch) for v in vessels]

    def consume_advisories(self) -> List[Dict[str, Any]]:
        with self._lock:
            out = list(self._advisories)
            self._advisories.clear()
            return out

    def track_keys_for_paths(self) -> Dict[int, str]:
        with self._lock:
            return {mmsi: (f"{mmsi}" if self._segment.get(mmsi, 0) == 0 else f"{mmsi}#{self._segment[mmsi]}") for mmsi in self._segment}


_tracker: Optional[AisMmsiIdentityTracker] = None
_tracker_lock = threading.Lock()


def get_mmsi_identity_tracker() -> AisMmsiIdentityTracker:
    global _tracker
    with _tracker_lock:
        if _tracker is None:
            _tracker = AisMmsiIdentityTracker()
        return _tracker

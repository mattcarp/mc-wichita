"""Voice channel watch states (live vs recorded vs not monitored)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _recorded_tile(mode: str, quiet: bool, capture_label: str, capture_time: Optional[str]) -> Dict[str, Any]:
    return {
        "mode": mode,
        "badge": "RECORDED",
        "headline": f"Recorded {capture_label}" if capture_label else "Recorded capture",
        "detail": "Quiet in that capture" if quiet else "Activity in that capture (not confirmed distress)",
        "capture_label": capture_label,
        "capture_time_utc": capture_time,
    }


def voice_channel_tiles(
    marine_watch: Optional[Dict[str, Any]],
    air_watch: Optional[Dict[str, Any]],
    capture_label: str,
    capture_time_utc: Optional[str],
    voice_live: bool,
) -> List[Dict[str, Any]]:
    marine = marine_watch or {}
    air = air_watch or {}

    def tile(
        channel_id: str,
        title: str,
        freq: str,
        recorded_quiet: bool,
    ) -> Dict[str, Any]:
        if voice_live:
            return {
                "id": channel_id,
                "title": title,
                "freq": freq,
                "mode": "live",
                "badge": "LIVE",
                "headline": "Listening live",
                "detail": "Quiet for now" if recorded_quiet else "Activity heard (not confirmed distress)",
            }
        rec = _recorded_tile("recorded", recorded_quiet, capture_label, capture_time_utc)
        return {
            "id": channel_id,
            "title": title,
            "freq": freq,
            "mode": "not_monitored",
            "badge": "OFF AIR",
            "headline": "Not monitored now",
            "detail": f"Receiver busy with AIS. Last recording ({rec['headline']}): {rec['detail']}",
            "recorded": rec,
        }

    air1215 = air.get("AIR_121p500MHz_distress") or next(
        (a for a in air.values() if isinstance(a, dict) and a.get("freq_mhz") == 121.5),
        None,
    )
    air1231 = next(
        (a for a in air.values() if isinstance(a, dict) and a.get("freq_mhz") and abs(a["freq_mhz"] - 123.1) < 0.05),
        None,
    )
    return [
        tile("ch16", "Channel 16", "156.800 MHz", (marine.get("ch16") or {}).get("quiet", True)),
        tile("ch09", "Channel 09", "156.450 MHz", (marine.get("ch09") or {}).get("quiet", True)),
        tile("guard1215", "121.5 guard", "121.500 MHz", (air1215 or {}).get("quiet", True)),
        tile("sar1231", "123.1 SAR", "123.100 MHz", (air1231 or {}).get("quiet", True)),
    ]

"""Source and freshness labels shared across live entities (ships, planes, satellites)."""

from __future__ import annotations

from typing import Any, Dict, Optional

SOURCE_OUR_ANTENNA = "our_antenna"
SOURCE_PUBLIC_FEED = "public_feed"
SOURCE_COMPUTED = "computed"

SOURCE_LABELS = {
    SOURCE_OUR_ANTENNA: "Heard by our antenna",
    SOURCE_PUBLIC_FEED: "Public feed",
    SOURCE_COMPUTED: "Computed, not observed",
}

# Align with wichita_ais_copy.freshness_bucket thresholds.
FRESHNESS_NOW_SEC = 120
FRESHNESS_RECENT_SEC = 600


def freshness_from_age(age_sec: Optional[float]) -> str:
    if age_sec is None:
        return "earlier"
    if age_sec < FRESHNESS_NOW_SEC:
        return "now"
    if age_sec < FRESHNESS_RECENT_SEC:
        return "recent"
    return "earlier"


def freshness_label(tier: str) -> str:
    return {
        "now": "Now",
        "recent": "Recent",
        "earlier": "Earlier",
        # legacy aliases
        "live": "Now",
        "stale": "Earlier",
    }.get(tier, "Earlier")


def provenance_fields(
    data_source: str,
    age_sec: Optional[float],
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tier = freshness_from_age(age_sec)
    out = {
        "data_source": data_source,
        "source_label": SOURCE_LABELS.get(data_source, data_source),
        "freshness": tier,
        "freshness_label": freshness_label(tier),
    }
    if extra:
        out.update(extra)
    return out

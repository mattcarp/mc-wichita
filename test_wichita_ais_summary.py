"""Summary counts and type breakdown share one source of truth."""

import os
import re
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)

os.environ.setdefault("WICHITA_CAPTURES_DIRS", str(FIXTURES))
os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)

from wichita_ais_copy import (
    freshness_bucket,
    harbour_summary_bundle,
    type_breakdown_phrase,
)


def test_type_breakdown_phrase_includes_others_when_more_than_three_types():
    counts = {
        "pleasure craft": 7,
        "passenger": 5,
        "sailing": 5,
        "high-speed craft": 2,
        "Unknown type": 1,
    }
    phrase = type_breakdown_phrase(counts)
    assert "7 pleasure craft" in phrase
    assert "5 passenger" in phrase
    assert "5 sailing" in phrase
    assert "and 3 others" in phrase
    assert "high-speed craft" not in phrase
    total = sum(counts.values())
    named = sum(counts[t] for t in ("pleasure craft", "passenger", "sailing"))
    assert named + 3 == total


def test_harbour_summary_bundle_headline_matches_breakdown():
    ships = []
    types = [
        ("pleasure craft", 7),
        ("passenger", 5),
        ("sailing", 5),
        ("high-speed craft", 2),
        ("Unknown type", 1),
    ]
    mmsi = 200000000
    for label, n in types:
        for _ in range(n):
            ships.append(
                {
                    "mmsi": mmsi,
                    "last_signal_s": 30,
                    "shiptype_label": label,
                    "is_base_station": False,
                }
            )
            mmsi += 1
    bundle = harbour_summary_bundle(ships, online=True, voice_not_monitored=False)
    assert bundle["nearby_now"] == 20
    assert sum(bundle["type_breakdown"].values()) == 20
    assert bundle["freshness_counts"]["now"] == 20
    assert "and 3 others" in bundle["text"]
    assert bundle["text"].startswith("20 nearby now")


def test_type_breakdown_matches_now_count_and_cards():
    import api_server

    client = TestClient(api_server.app)
    res = client.get("/api/live-ais/snapshot")
    assert res.status_code == 200
    body = res.json()
    now_count = body["nearby_now"]
    assert now_count == body["freshness_counts"]["now"]
    breakdown = body.get("type_breakdown") or {}
    assert sum(breakdown.values()) == now_count
    cards_now = [s for s in body["ships"] if freshness_bucket(s.get("last_signal_s")) == "now"]
    assert len(cards_now) == now_count
    for s in cards_now:
        label = s.get("shiptype_label") or "vessels"
        assert breakdown.get(label, 0) >= 1
    summary = body.get("summary") or ""
    m = re.search(r"^(\d+) nearby now \((.+)\)", summary)
    assert m, summary
    assert int(m.group(1)) == now_count
    inner = m.group(2).split(";")[0]
    others = re.search(r"and (\d+) others", inner)
    if others:
        top_part = inner.split(", and ")[0]
        top_sum = sum(int(x.split()[0]) for x in top_part.split(", ") if x.split()[0].isdigit())
        assert top_sum + int(others.group(1)) == now_count

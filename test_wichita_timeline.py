"""Live event log presentation and pagination."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wichita_timeline import paginate_events, prepare_timeline_events

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "live_events"


def _write_large_event_log(root: Path, n: int = 120) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"events-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    now = datetime.now(timezone.utc)
    lines = []
    for i in range(n):
        ts = now - timedelta(minutes=i * 20)
        kind = "ship_status_change" if i % 2 == 0 else "ship_first_heard"
        lines.append(
            json.dumps(
                {
                    "ts_utc": ts.isoformat(),
                    "kind": kind,
                    "sentence": f"SHIP{i} event.",
                    "display_name": f"SHIP{i}",
                }
            )
        )
    lines.append(
        json.dumps(
            {
                "ts_utc": now.isoformat(),
                "kind": "receiver_up",
                "sentence": "AIS receiver came back online.",
            }
        )
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_prepare_merges_quiet_events():
    raw = [
        {"ts_utc": "2026-10-09T21:12:00+00:00", "kind": "ship_silent", "sentence": "A quiet.", "display_name": "A"},
        {"ts_utc": "2026-10-09T21:14:00+00:00", "kind": "ship_silent", "sentence": "B quiet.", "display_name": "B"},
        {"ts_utc": "2026-10-09T21:10:00+00:00", "kind": "receiver_up", "sentence": "Up."},
    ]
    out = prepare_timeline_events(raw)
    assert any(e.get("kind") == "ship_silent_group" for e in out)
    assert out[0]["kind"] == "receiver_up"


def test_events_page_limits_and_cursor(tmp_path, monkeypatch):
    monkeypatch.setenv("WICHITA_EVENTS_DIR", str(tmp_path))
    _write_large_event_log(tmp_path, 80)
    from wichita_live_events import get_engine

    engine = get_engine()
    page1 = engine.events_page(hours=24, limit=20)
    assert len(page1["events"]) == 20
    assert page1["has_more"] is True
    page2 = engine.events_page(hours=24, limit=20, before=page1["next_before"])
    assert len(page2["events"]) == 20
    merged = paginate_events(prepare_timeline_events(engine.read_events(24)), limit=20)
    assert len(merged["events"]) <= 20

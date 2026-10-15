#!/usr/bin/env python3
"""Append rtl_airband channel stats to a CSV once a minute.

Receive-only, no audio: logs noise floor, signal level, squelch threshold and the
cumulative squelch/activity counters, so antenna changes can be measured before and
after. Counters reset when rtl_airband restarts; compare deltas within one run.

Usage: airband_baseline.py STATS_FILE CSV_FILE [--once] [--interval SEC]
"""
from __future__ import annotations

import argparse
import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path

FIELDS = (
    "channel_dbfs_noise_level",
    "channel_dbfs_signal_level",
    "channel_squelch_level",
    "channel_noise_level",
    "channel_squelch_counter",
    "channel_activity_counter",
    "channel_flappy_counter",
)
LINE = re.compile(r'^(\w+)\{freq="([\d.]+)"\}\s+(\S+)$')


def parse_stats(text: str) -> dict:
    """Return {freq: {metric: float}} from rtl_airband's Prometheus-style stats file."""
    out: dict = {}
    for raw in text.splitlines():
        m = LINE.match(raw.strip())
        if m and m.group(1) in FIELDS:
            out.setdefault(m.group(2), {})[m.group(1)] = float(m.group(3))
    return out


def rows(stats: dict, stats_mtime: float) -> list:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mtime = datetime.fromtimestamp(stats_mtime, timezone.utc).isoformat(timespec="seconds")
    return [
        {"observed_utc": now, "stats_mtime_utc": mtime, "freq_mhz": freq,
         **{f: metrics.get(f, "") for f in FIELDS}}
        for freq, metrics in sorted(stats.items())
    ]


def append(csv_path: Path, new_rows: list) -> None:
    fresh = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=("observed_utc", "stats_mtime_utc", "freq_mhz") + FIELDS)
        if fresh:
            w.writeheader()
        w.writerows(new_rows)


def sample(stats_path: Path, csv_path: Path) -> int:
    if not stats_path.exists():
        return 0
    new = rows(parse_stats(stats_path.read_text(encoding="utf-8")), stats_path.stat().st_mtime)
    if new:
        append(csv_path, new)
    return len(new)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stats", type=Path)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=60.0)
    a = ap.parse_args()
    while True:
        sample(a.stats, a.csv)
        if a.once:
            return
        time.sleep(a.interval)


if __name__ == "__main__":
    main()

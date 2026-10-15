"""airband_baseline against a real rtl_airband stats capture from the Mini (2026-10-15)."""
import csv
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "airband_baseline", Path(__file__).parent / "ops" / "ground-voice" / "airband_baseline.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

# Captured verbatim from ~/wichita/live/airband/stats.txt on matts-mac-mini, 2026-10-15.
REAL = (Path(__file__).parent / "ops" / "ground-voice" / "stats_sample_20261015.txt").read_text()


def test_parse_real_stats():
    s = ab.parse_stats(REAL)
    assert list(s) == ["156.800"]
    assert s["156.800"]["channel_dbfs_noise_level"] < -20
    assert s["156.800"]["channel_squelch_level"] > 0
    assert "buffer_overflow_count" not in s["156.800"]


def test_sample_appends_one_header(tmp_path):
    stats = tmp_path / "stats.txt"
    stats.write_text(REAL)
    out = tmp_path / "baseline.csv"
    assert ab.sample(stats, out) == 1
    assert ab.sample(stats, out) == 1
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 2
    assert rows[0]["freq_mhz"] == "156.800"
    assert rows[0]["observed_utc"].endswith("+00:00")


def test_missing_stats_file_writes_nothing(tmp_path):
    out = tmp_path / "baseline.csv"
    assert ab.sample(tmp_path / "absent.txt", out) == 0
    assert not out.exists()

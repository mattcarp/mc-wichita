"""ICAO airband channel naming and LMML table."""

import json
from pathlib import Path

import pytest

from wichita_airband_channel import (
    InvalidAirbandChannel,
    channel_name_from_hz,
    classify_spacing,
    load_lmml_channels,
    nearest_lmml_channel_mhz,
    parse_channel_name,
    tuning_hz_from_channel_name,
)


@pytest.mark.parametrize(
    "name,spacing",
    [
        ("118.000", "25k"),
        ("118.025", "25k"),
        ("118.050", "25k"),
        ("121.500", "25k"),
        ("135.100", "25k"),
    ],
)
def test_25khz_channels(name, spacing):
    parsed = parse_channel_name(name)
    assert parsed.spacing == spacing
    assert parsed.tuning_hz == int(round(parsed.name_mhz * 1_000_000))


@pytest.mark.parametrize(
    "name",
    [
        "118.005",
        "118.010",
        "121.605",
        "128.155",
        "135.105",
        "127.005",
        "127.405",
    ],
)
def test_833khz_channels(name):
    parsed = parse_channel_name(name)
    assert parsed.spacing == "8.33k"
    assert parsed.name_str == name


@pytest.mark.parametrize("name", ["117.995", "137.001", "118", "118.00", "12.8005", "abc"])
def test_invalid_names(name):
    with pytest.raises(InvalidAirbandChannel):
        parse_channel_name(name)


def test_round_trip_hz():
    hz = tuning_hz_from_channel_name("128.155")
    assert hz == 128_155_000
    assert channel_name_from_hz(hz) == "128.155"


def test_25k_name_from_hz_requires_grid():
    with pytest.raises(InvalidAirbandChannel):
        channel_name_from_hz(118_005_000, spacing="25k")


def test_lmml_table_has_metadata():
    data = load_lmml_channels()
    assert data["airport_icao"] == "LMML"
    aip = data["aip"]
    assert "source_url" in aip
    assert "airac_effective_date" in aip
    assert "retrieved_at_utc" in aip
    ids = {c["id"] for c in data["channels"]}
    assert "lmml-twr" in ids
    assert "lmml-info" in ids
    info = next(c for c in data["channels"] if c["id"] == "lmml-info")
    assert info["aip_verified"] is False


def test_nearest_lmml_channel():
    data = load_lmml_channels()
    chs = data["channels"]
    hit = nearest_lmml_channel_mhz(135.104, chs)
    assert hit and hit["id"] == "lmml-twr"


def test_lmml_json_matches_repo():
    path = Path(__file__).parent / "config" / "lmml_airband_channels.json"
    assert path.is_file()
    json.loads(path.read_text(encoding="utf-8"))
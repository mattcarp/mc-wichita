import wichita_mmsi as m


def test_decode_ship_malta():
    d = m.decode_mmsi(248000662)
    assert d["kind"] == "ship" and d["mid"] == "248" and d["mid_country"] == "Malta"


def test_decode_patterns():
    assert m.decode_mmsi(2150200)["kind"] == "coast_station"  # 002150200
    assert m.decode_mmsi(2150200)["mid_country"] == "Malta"
    assert m.decode_mmsi(111248123)["kind"] == "sar_aircraft"
    assert m.decode_mmsi(992481234)["kind"] == "aton"
    assert m.decode_mmsi(992486234)["kind_label"].startswith("Virtual")
    assert m.decode_mmsi(970123456)["kind"] == "sart"
    assert m.decode_mmsi(24800066)["kind"] == "group"


def test_registry_merge_persists(tmp_path):
    p = tmp_path / "reg.json"
    m.update_registry([{"mmsi": 248000662, "shipname": "KATALEYA", "to_bow": 20, "to_stern": 10, "to_port": 4, "to_starboard": 4}], p)
    m.update_registry([{"mmsi": 248000662, "shipname": "", "callsign": "9HB3841", "imo": 0}], p)
    info = m.lookup(248000662, m.load_registry(p))
    st = info["static"]
    assert st["shipname"] == "KATALEYA" and st["callsign"] == "9HB3841"
    assert st["length_m"] == 30 and st["beam_m"] == 8 and "imo" not in st

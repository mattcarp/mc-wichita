from wichita_ais_patterns import AisPatternObserver, in_harbour


def test_harbour_arrival_emits_observation():
    events = []

    def emit(kind, sentence, **fields):
        events.append((kind, sentence, fields))

    obs = AisPatternObserver(emit)
    outside = {
        "mmsi": 1,
        "lat": 35.95,
        "lon": 14.4,
        "speed_kn": 8,
        "display_name": "FERRY",
        "shiptype_category": "passenger",
        "is_base_station": False,
    }
    inside = {**outside, "lat": 35.89, "lon": 14.51}
    obs.ingest([outside], poll_sec=5)
    assert in_harbour(outside["lat"], outside["lon"]) is False
    obs.ingest([inside], poll_sec=5)
    kinds = [e[0] for e in events]
    assert "pattern_arrival" in kinds
    assert events[-1][1].startswith("Observation")

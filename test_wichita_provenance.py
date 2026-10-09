from wichita_provenance import SOURCE_OUR_ANTENNA, freshness_from_age, provenance_fields


def test_freshness_tiers():
    assert freshness_from_age(30) == "live"
    assert freshness_from_age(200) == "recent"
    assert freshness_from_age(2000) == "stale"


def test_provenance_labels():
    p = provenance_fields(SOURCE_OUR_ANTENNA, 10)
    assert p["source_label"] == "Heard by our antenna"
    assert p["freshness_label"] == "Live"

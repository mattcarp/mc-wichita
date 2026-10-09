import wichita_ais_copy as copy


def test_decode_mtspb():
    name, raw, ok = copy.decode_destination("MTSPB")
    assert ok
    assert name == "Marsaxlokk / Freeport"
    assert raw == "MTSPB"


def test_lead_sentence_underway():
    s = copy.lead_sentence(
        nav_status=0,
        speed_kn=10.2,
        cog_deg=220,
        destination_raw="MTSPB",
        destination_name="Marsaxlokk / Freeport",
        destination_decoded=True,
        shiptype_label="passenger",
    )
    assert "10.2 kn" in s
    assert "Marsaxlokk" in s


def test_first_heard_sentence():
    s = {
        "display_name": "GLISS",
        "mmsi": 123,
        "mmsi_display": "000000123",
        "shiptype_label": "sailing",
        "shiptype_code": 36,
        "destination_display": "Valletta",
    }
    text = copy.first_heard_sentence(s)
    assert "GLISS" in text
    assert "sailing yacht" in text
    assert "heading for Valletta" in text
    assert "(sailing)" not in text


def test_first_heard_unnamed():
    s = {
        "display_name": "Unnamed, MMSI 232031859",
        "mmsi": 232031859,
        "mmsi_display": "232031859",
        "shiptype_label": "sailing",
        "shiptype_code": 36,
    }
    text = copy.first_heard_sentence(s)
    assert "An unnamed vessel" in text
    assert "232031859" in text


def test_unknown_destination_not_invented():
    name, raw, ok = copy.decode_destination("ZZZZZ")
    assert not ok
    s = copy.lead_sentence(
        nav_status=5,
        speed_kn=0,
        cog_deg=None,
        destination_raw=raw,
        destination_name=name,
        destination_decoded=ok,
        shiptype_label="high-speed craft",
    )
    assert "Moored" in s
    assert ok is False

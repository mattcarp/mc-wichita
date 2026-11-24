"""Airband ADS-B guess helper."""

from wichita_airband_adsb import guess_payload


def test_guess_labels_and_caveat():
    planes = [
        {
            "hex": "4ca123",
            "callsign": "RYR123",
            "display_name": "RYR123",
            "lat": 35.88,
            "lon": 14.50,
            "altitude_ft": 2500,
            "last_signal_s": 10,
        }
    ]
    out = guess_payload(135.105, planes=planes)
    assert "guess" in out["likely_aircraft_sentence"]
    assert out["likely_aircraft"]
    assert out["lmml_channel_label"]


def test_no_planes_nearby():
    out = guess_payload(121.5, planes=[])
    assert "none near LMML" in out["likely_aircraft_sentence"]
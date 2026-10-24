"""Aircraft of interest: rules, lookup, watch-list alerts."""

from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "live_adsb"
SEAWOLF_HEX = "4caabc"


@pytest.fixture
def interest_env(tmp_path, monkeypatch):
    interests = tmp_path / "interests.json"
    monkeypatch.setenv("WICHITA_INTERESTS_FILE", str(interests))
    monkeypatch.setenv("WICHITA_ADSBLOL", "0")
    monkeypatch.setenv("WICHITA_ADSB_FIXTURE_DIR", str(FIXTURE))
    import wichita_aircraft_interest as wai
    import wichita_interest as wi

    wi._engine = None  # noqa: SLF001
    wai._engine = None  # noqa: SLF001
    return interests


def test_default_rules_seeded(interest_env):
    import wichita_aircraft_interest as wai

    rules = wai.list_aircraft_rules()
    kinds = {r["kind"] for r in rules}
    assert "close_low" in kinds
    assert "emergency_squawk" in kinds
    assert "loiter" in kinds


def test_lookup_by_hex(interest_env):
    import wichita_adsb_live as wad
    import wichita_aircraft_interest as wai

    planes = wad.live_adsb_snapshot()["aircraft"]
    cands = wai.lookup_aircraft_candidates("4caabc", planes)
    assert cands and cands[0]["hex"] == SEAWOLF_HEX


def test_enrich_adds_range_nm(interest_env):
    import wichita_adsb_live as wad
    import wichita_aircraft_interest as wai

    snap = wai.enrich_adsb_snapshot(wad.live_adsb_snapshot())
    ryr = next(p for p in snap["aircraft"] if p["hex"] == SEAWOLF_HEX)
    assert ryr.get("range_nm") is not None
    assert ryr.get("interest_alert") is not True  # high altitude; not close-low


def test_emergency_squawk_rule(interest_env):
    import wichita_adsb_live as wad
    import wichita_aircraft_interest as wai

    snap = wai.enrich_adsb_snapshot(wad.live_adsb_snapshot())
    em = next(p for p in snap["aircraft"] if p.get("squawk") == "7700")
    assert em.get("interest_alert") is True


def test_watch_list_heard_alert_once(interest_env):
    import wichita_adsb_live as wad
    import wichita_aircraft_interest as wai

    wai.add_flight(hex_id=SEAWOLF_HEX, callsign="RYR82LT", label="RYR test")
    events = []

    def capture(kind, sentence, **fields):
        events.append((kind, sentence, fields))

    engine = wai.get_aircraft_interest_engine(capture)
    planes = wad.live_adsb_snapshot()["aircraft"]
    engine.ingest_planes(planes)
    engine.ingest_planes([])
    engine._in_reception["seawolf"] = False  # noqa: SLF001 — force re-arm path
    engine._armed[list(engine._armed.keys())[0]] = True  # noqa: SLF001
    engine.ingest_planes(planes)
    kinds = [e[0] for e in events if e[0] == "aircraft_of_interest_seen"]
    assert len(kinds) >= 1
    engine.ingest_planes(planes)
    assert len([e for e in events if e[0] == "aircraft_of_interest_seen"]) == 1


def test_interest_api_flights(interest_env):
    from fastapi.testclient import TestClient

    import api_server

    client = TestClient(api_server.app)
    res = client.post("/api/interests/flights", json={"hex": "4d20a2", "callsign": "TEST7700"})
    assert res.status_code == 200
    listed = client.get("/api/interests/flights").json()
    assert len(listed["flights"]) == 1
    rules = client.get("/api/interests/aircraft/rules").json()
    assert len(rules["rules"]) >= 3
    summary = client.get("/api/interests").json()
    assert "flights" in summary and "aircraft_rules" in summary
    fid = listed["flights"][0]["id"]
    assert client.delete(f"/api/interests/flights/{fid}").status_code == 200

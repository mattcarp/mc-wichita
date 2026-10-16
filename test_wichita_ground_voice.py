import json, os, time
import pytest
import wichita_ground_voice as gv


@pytest.mark.parametrize("f", [145.5, 433.5, 27.065, 156.8, 121.5, 446.00625, 446.01875, 446.03125, 446.04375, 446.05625, 446.06875, 446.08125, 446.09375])
def test_allowlisted_frequencies_pass(f):
    gv.check_frequency(f)


@pytest.mark.parametrize("f", [380.0, 390.5, 445.99375, 446.1, 446.10625, 900.0, 1890.0, 156.65, 135.1, 118.0, 162.025])
def test_forbidden_or_unlisted_rejected(f):
    with pytest.raises(gv.NotAllowed):
        gv.check_frequency(f)


def test_allowlist_is_exactly_the_malta_set():
    assert set(gv.CHANNELS) == {"ham-2m-calling", "ham-70cm-calling", "cb-ch9", "marine-ch16", "air-121-5"} | {f"pmr446-ch{n}" for n in range(1, 9)}
    with pytest.raises(gv.NotAllowed):
        gv.get_channel("tetra-1")


def test_cap_per_channel_and_total():
    lim = gv.ListenerLimiter(per_channel=2, total=3)
    lim.acquire("cb-ch9"); lim.acquire("cb-ch9")
    with pytest.raises(gv.ListenerLimit, match="channel"):
        lim.acquire("cb-ch9")
    lim.acquire("marine-ch16")
    with pytest.raises(gv.ListenerLimit, match="overall"):
        lim.acquire("air-121-5")
    lim.release("cb-ch9")
    lim.acquire("air-121-5")
    assert lim.count() == 3


def test_limit_state_shown(tmp_path):
    lim = gv.ListenerLimiter(per_channel=1, total=5)
    lim.acquire("cb-ch9")
    st = {c["id"]: c for c in gv.channel_status({"cb-ch9": "http://127.0.0.1/x"}, lim, cleared=True)}
    assert st["cb-ch9"]["state"] == "limit"
    assert st["marine-ch16"]["state"] == "idle"


def test_metadata_never_contains_source_urls(tmp_path):
    src = tmp_path / "s.json"
    src.write_text(json.dumps({"marine-ch16": "http://100.114.183.100:8000/ch16.mp3"}))
    sources = gv.load_private_sources(str(src))
    blob = json.dumps(gv.channel_status(sources, cleared=True))
    assert "100.114" not in blob and "http" not in blob
    assert {c["id"]: c["state"] for c in json.loads(blob)}["marine-ch16"] == "live"


def test_idle_until_legally_cleared():
    st = gv.channel_status({"marine-ch16": "http://127.0.0.1/x"}, cleared=False)
    assert all(c["state"] == "idle" for c in st)


def test_private_sources_drop_bad_entries(tmp_path):
    src = tmp_path / "s.json"
    src.write_text(json.dumps({
        "marine-ch16": "http://100.114.183.100:8000/a",
        "cb-ch9": "http://example.com/a",          # not our receiver
        "air-121-5": "file:///etc/passwd",          # bad scheme
        "tetra": "http://127.0.0.1/t",              # not allowlisted
    }))
    assert gv.load_private_sources(str(src)) == {"marine-ch16": "http://100.114.183.100:8000/a"}


def test_tickets_one_time_and_channel_bound():
    t = gv.Tickets()
    tok = t.mint("cb-ch9")
    assert not t.redeem(tok, "marine-ch16")
    tok = t.mint("cb-ch9")
    assert t.redeem(tok, "cb-ch9") and not t.redeem(tok, "cb-ch9")


def test_pipeline_keeps_scores_drops_audio(tmp_path):
    wav = tmp_path / "a.wav"; wav.write_bytes(b"RIFF")
    ev = gv.submit_segment("marine-ch16", str(wav), time.time(), scorer=lambda p, f: 20, base=tmp_path / "gv")
    assert ev["clip"] is None and not wav.exists()
    assert not (tmp_path / "gv" / "clips").exists()


def test_pipeline_keeps_flagged_clip_72h(tmp_path):
    wav = tmp_path / "a.wav"; wav.write_bytes(b"RIFF")
    base = tmp_path / "gv"
    ev = gv.submit_segment("marine-ch16", str(wav), time.time(), scorer=lambda p, f: 90, base=base)
    clip = base / "clips" / ev["clip"]
    assert clip.exists()
    assert gv.purge_expired(base, now=time.time() + 71 * 3600) == 0
    assert gv.purge_expired(base, now=time.time() + 73 * 3600) == 1


def test_routes_split(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from wichita_ground_voice_routes import router
    src = tmp_path / "s.json"
    src.write_text(json.dumps({"marine-ch16": "http://127.0.0.1:9/a"}))
    monkeypatch.setenv("WICHITA_GROUND_VOICE_SOURCES", str(src))
    app = FastAPI(); app.include_router(router); c = TestClient(app)
    r = c.get("/api/ground-voice/channels")
    assert r.status_code == 200 and "127.0.0.1" not in r.text
    assert c.post("/api/ground-voice/channels/marine-ch16/ticket").status_code == 409  # not cleared
    assert c.get("/api/ground-voice/listen/tetra?ticket=x").status_code == 404
    assert c.get("/api/ground-voice/listen/marine-ch16?ticket=bad").status_code == 401
    monkeypatch.setenv("WICHITA_GROUND_VOICE_CLEARED", "true")
    tok = c.post("/api/ground-voice/channels/marine-ch16/ticket").json()["ticket"]
    assert c.get(f"/api/ground-voice/listen/marine-ch16?ticket={tok}").status_code == 502
    assert gv.LIMITER.count() == 0  # released after failure


def test_unreachable_receiver_is_idle():
    st = {c["id"]: c for c in gv.channel_status({"marine-ch16": "http://127.0.0.1/x"}, cleared=True, reachable=[])}
    assert st["marine-ch16"]["state"] == "idle" and "not answering" in st["marine-ch16"]["reason"]


def test_pmr446_is_eight_nfm_channels_at_12_5_khz_steps():
    ch = [gv.CHANNELS[f"pmr446-ch{n}"] for n in range(1, 9)]
    assert [c.frequency_mhz for c in ch] == [446.00625, 446.01875, 446.03125, 446.04375,
                                              446.05625, 446.06875, 446.08125, 446.09375]
    assert all(c.mode == "NFM" for c in ch)


@pytest.mark.parametrize("f", [380.0, 390.5, 1890.0, 900.0, 1900.0])
def test_tetra_dect_phones_still_refused(f):
    with pytest.raises(gv.NotAllowed):
        gv.check_frequency(f)

from datetime import datetime, timezone

from wichita_track_signal import (
    STATUS_LIVE,
    STATUS_SIGNAL_LOST,
    STATUS_STALE,
    ADSB_LIVE_SEC,
    AIS_CLASS_A_LIVE_SEC,
    AIS_CLASS_B_LIVE_SEC,
    apply_track_signal_fields,
    classify_age,
    feed_stalled,
    process_paths_geojson,
    projected_position,
    split_coords_at_speed_jumps,
    split_coords_at_time_gaps,
    split_adsb_track_points,
)


def test_classify_ais_thresholds():
    assert classify_age(10, AIS_CLASS_A_LIVE_SEC, 200, 600) == STATUS_LIVE
    assert classify_age(AIS_CLASS_B_LIVE_SEC + 1, AIS_CLASS_B_LIVE_SEC, 300, 900) == STATUS_STALE
    assert classify_age(900, 45, 200, 600) == STATUS_SIGNAL_LOST


def test_classify_adsb():
    assert classify_age(ADSB_LIVE_SEC, ADSB_LIVE_SEC, 45, 120) == STATUS_LIVE
    assert classify_age(100, ADSB_LIVE_SEC, 45, 120) == STATUS_SIGNAL_LOST


def test_feed_stall_downgrades_lost_cue():
    ship = {"lat": 35.9, "lon": 14.5, "last_signal_s": 9999, "last_heard_utc": "x"}
    apply_track_signal_fields(ship, kind="ais", ais_class="class_b", feed_stalled=True)
    assert ship["track_signal_status"] == STATUS_STALE
    assert ship["track_signal_reason"] == "feed_stall"
    assert ship["sudden_silence_cue"] is False


def test_sudden_silence_cue_when_entity_dark():
    ship = {"lat": 35.9, "lon": 14.5, "last_signal_s": 1200, "last_heard_utc": "x", "speed_kn": 10, "cog_deg": 90}
    apply_track_signal_fields(ship, kind="ais", ais_class="class_b", feed_stalled=False)
    assert ship["track_signal_status"] == STATUS_SIGNAL_LOST
    assert ship["sudden_silence_cue"] is True


def test_split_time_gaps():
    coords = [[14.5, 35.9], [14.51, 35.91], [14.52, 35.92]]
    times = [0.0, 100.0, 500.0]
    segs = split_coords_at_time_gaps(coords, times, gap_sec=200)
    assert len(segs) == 2
    assert len(segs[0]) == 2
    assert len(segs[1]) == 1


def test_split_impossible_speed():
    coords = [[14.5, 35.9], [15.0, 36.0]]
    times = [0.0, 60.0]
    segs = split_coords_at_speed_jumps(coords, times, max_speed_kn=40, min_dt_sec=30)
    assert len(segs) == 2


def test_process_paths_geojson_splits():
    geo = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"mmsi": 123, "timestamps_start": [0, 100, 500]},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[14.5, 35.9], [14.51, 35.91], [14.52, 35.92]],
                },
            }
        ],
    }
    out = process_paths_geojson(geo, gap_sec=200, split_speed_jump=False)
    assert out["features"][0]["properties"].get("track_gap_split") is True
    assert len(out["features"][0]["geometry"]["coordinates"]) == 2


def test_projected_position_capped():
    proj = projected_position(35.9, 14.5, 10, 90, 30, max_sec=60)
    assert proj and proj["projected"] is True
    assert projected_position(35.9, 14.5, 10, 90, 90, max_sec=60) is None


def test_feed_stalled_states():
    assert feed_stalled(online=False, receiver_health={"state": "live"}) is True
    assert feed_stalled(online=True, receiver_health={"state": "stale"}) is True
    assert feed_stalled(online=True, receiver_health={"state": "live"}) is False


def test_adsb_track_point_split():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    t1 = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc).isoformat()
    pts = [{"ts_utc": t0, "lat": 1, "lon": 2}, {"ts_utc": t1, "lat": 1.1, "lon": 2.1}]
    segs = split_adsb_track_points(pts, gap_sec=60)
    assert len(segs) == 2

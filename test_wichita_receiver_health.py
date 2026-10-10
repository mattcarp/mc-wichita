from wichita_receiver_health import (
    STATE_LIVE,
    STATE_STALE,
    STATE_UNREACHABLE,
    feed_health_payload,
    feed_health_state,
    heard_last_60s_badge,
)


def test_feed_stale_after_10s():
    assert feed_health_state(online=True, error=None, youngest_signal_s=11.0) == STATE_STALE
    assert feed_health_state(online=True, error=None, youngest_signal_s=5.0) == STATE_LIVE


def test_unreachable_offline():
    assert feed_health_state(online=False, error="receiver offline", youngest_signal_s=None) == STATE_UNREACHABLE


def test_empty_healthy_is_quiet():
    h = feed_health_payload(
        receiver="AIS-catcher",
        band="AIS",
        online=True,
        error=None,
        youngest_signal_s=2.0,
        entity_count=0,
    )
    assert h["quiet"] is True
    assert h["coverage"] == "quiet"


def test_heard_badge_counts():
    badge = heard_last_60s_badge(ais_count=2, adsb_count=1)
    assert badge["count"] == 3
    assert badge["active"] is True

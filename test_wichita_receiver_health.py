from wichita_receiver_health import (
    ais_course_is_unknown,
    ais_speed_is_unknown,
    classify_receiver_state,
    sanitize_ais_motion,
    STATE_QUIET,
    STATE_LIVE,
    STATE_UNREACHABLE,
)


def test_ais_not_available_motion():
    m = sanitize_ais_motion(102.3, 360, 511)
    assert m["speed_unknown"] is True
    assert m["cog_unknown"] is True
    assert m["speed_kn"] is None
    assert m["cog_deg"] is None


def test_quiet_healthy_feed():
    state = classify_receiver_state(
        reachable=True,
        payload_valid=True,
        feed_age_sec=2.0,
        contact_count=0,
    )
    assert state == STATE_QUIET


def test_unreachable():
    state = classify_receiver_state(
        reachable=False,
        payload_valid=False,
        feed_age_sec=None,
        contact_count=0,
    )
    assert state == STATE_UNREACHABLE


def test_live_with_contacts():
    state = classify_receiver_state(
        reachable=True,
        payload_valid=True,
        feed_age_sec=3.0,
        contact_count=2,
    )
    assert state == STATE_LIVE


def test_speed_boundary():
    assert ais_speed_is_unknown(102.3) is True
    assert ais_speed_is_unknown(12.0) is False
    assert ais_course_is_unknown(360) is True
    assert ais_course_is_unknown(180) is False

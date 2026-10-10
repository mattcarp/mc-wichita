from wichita_ais_nav import (
    AIS_COURSE_NOT_AVAILABLE_DEG,
    AIS_SPEED_NOT_AVAILABLE_KN,
    normalize_ais_course,
    normalize_ais_speed,
)


def test_speed_not_available():
    v, known = normalize_ais_speed(AIS_SPEED_NOT_AVAILABLE_KN)
    assert v is None
    assert known is False


def test_course_not_available():
    v, known = normalize_ais_course(AIS_COURSE_NOT_AVAILABLE_DEG)
    assert v is None
    assert known is False


def test_real_speed_preserved():
    v, known = normalize_ais_speed(12.4)
    assert v == 12.4
    assert known is True

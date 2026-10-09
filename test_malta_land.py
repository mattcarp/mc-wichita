import wichita_malta_land as ml


def test_sea_points_not_on_land():
    for lon, lat, label in ml.SEA_POINTS:
        assert not ml.point_on_land(lon, lat), label


def test_land_points_on_land():
    for lon, lat, label in ml.LAND_POINTS:
        assert ml.point_on_land(lon, lat), label


def test_moving_moored_partition():
    from wichita_ais_copy import movement_counts

    ships = [
        {"last_signal_s": 10, "speed_kn": 5},
        {"last_signal_s": 20, "speed_kn": 0},
        {"last_signal_s": 200, "speed_kn": 8},
        {"last_signal_s": 5, "speed_kn": 0.2},
    ]
    mc = movement_counts(ships)
    assert mc["now"] == 3
    assert mc["moving"] + mc["moored_or_slow"] == mc["now"]
    assert mc["moving"] == 1
    assert mc["moored_or_slow"] == 2

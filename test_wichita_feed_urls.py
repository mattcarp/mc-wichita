import pytest

from wichita_feed_urls import assert_private_feed_url


def test_localhost_ok():
    assert_private_feed_url("http://127.0.0.1:8100/api/ships.json", env_name="TEST")


def test_public_rejected(monkeypatch):
    monkeypatch.delenv("WICHITA_ALLOW_PUBLIC_FEED_URLS", raising=False)
    with pytest.raises(ValueError):
        assert_private_feed_url("http://example.com/ships.json", env_name="TEST")


def test_tailnet_cgnat_feed_url_allowed():
    from wichita_feed_urls import validated_feed_url

    assert validated_feed_url("http://100.114.183.100:8100", "WICHITA_AIS_URL", "") == "http://100.114.183.100:8100"

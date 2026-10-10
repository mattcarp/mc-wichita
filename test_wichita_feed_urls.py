import pytest

from wichita_feed_urls import assert_private_feed_url


def test_localhost_ok():
    assert_private_feed_url("http://127.0.0.1:8100/api/ships.json", env_name="TEST")


def test_public_rejected(monkeypatch):
    monkeypatch.delenv("WICHITA_ALLOW_PUBLIC_FEED_URLS", raising=False)
    with pytest.raises(ValueError):
        assert_private_feed_url("http://example.com/ships.json", env_name="TEST")

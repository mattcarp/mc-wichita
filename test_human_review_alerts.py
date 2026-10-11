import json
import sys
import types
from pathlib import Path

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules["api_maritime_aviation"] = api_maritime_aviation_stub

from fastapi.testclient import TestClient

import api_server
import alert_store


client = TestClient(api_server.app)


def setup_function() -> None:
    api_server.ALERTS.clear()
    store = alert_store.alerts_jsonl_path()
    if store.is_file():
        store.unlink()


def test_create_alert_pending_review_no_auto_dispatch(monkeypatch) -> None:
    telegram_calls = []
    discord_calls = []
    mc_calls = []
    spotify_calls = []

    monkeypatch.setattr(
        api_server,
        "send_stress_alert",
        lambda *a, **k: telegram_calls.append((a, k)) or True,
    )
    monkeypatch.setattr(
        api_server,
        "send_discord_alert",
        lambda *a, **k: discord_calls.append((a, k)) or True,
    )
    monkeypatch.setattr(
        api_server,
        "_dispatch_alert_to_mission_control",
        lambda alert: mc_calls.append(alert.id),
    )
    monkeypatch.setattr(
        api_server,
        "_dispatch_spotify_audio_alert",
        lambda alert, stress: spotify_calls.append(alert.id) or True,
    )

    response = client.post(
        "/alerts",
        json={
            "title": "Voice stress event",
            "transcript": "Heavy breathing on channel 16",
            "metadata": {"stress_score": 88},
            "frequency_hz": 156800000,
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_status"] == "pending_review"
    assert telegram_calls == []
    assert discord_calls == []
    assert mc_calls == []
    assert spotify_calls == []

    store_path = alert_store.alerts_jsonl_path()
    assert store_path.is_file()
    lines = store_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["id"] == payload["id"]
    assert persisted["review_status"] == "pending_review"


def test_confirm_sends_telegram_only(monkeypatch) -> None:
    sent = []

    def fake_send(stress_score, frequency, transcription, indicators):
        sent.append(
            {
                "stress_score": stress_score,
                "frequency": frequency,
                "transcription": transcription,
            }
        )
        return True

    monkeypatch.setattr(api_server, "send_stress_alert", fake_send)
    monkeypatch.setattr(
        api_server,
        "send_discord_alert",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("discord must not run")),
    )

    created = client.post(
        "/alerts",
        json={
            "title": "Stress pending",
            "metadata": {"stress_score": 81},
            "transcript": "Need help now",
            "source": "wichita-sdr",
        },
    ).json()

    confirm = client.post(f"/alerts/{created['id']}/confirm")
    assert confirm.status_code == 200
    assert confirm.json()["review_status"] == "confirmed"
    assert len(sent) == 1
    assert sent[0]["stress_score"] == 81


def test_dismiss_does_not_notify(monkeypatch) -> None:
    monkeypatch.setattr(
        api_server,
        "send_stress_alert",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("telegram must not run")),
    )

    created = client.post(
        "/alerts",
        json={"title": "Routine", "source": "wichita-sdr"},
    ).json()

    dismissed = client.post(
        f"/alerts/{created['id']}/dismiss",
        json={"note": "False alarm"},
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["review_status"] == "dismissed"
    assert dismissed.json()["review_note"] == "False alarm"


def test_alerts_reload_from_disk_after_restart(monkeypatch) -> None:
    monkeypatch.setattr(api_server, "send_stress_alert", lambda *a, **k: True)

    created = client.post(
        "/alerts",
        json={
            "title": "Persist me",
            "metadata": {"stress_score": 72},
            "source": "wichita-sdr",
        },
    ).json()

    api_server.ALERTS.clear()
    api_server._bootstrap_alerts_from_disk()

    listed = client.get("/alerts").json()
    assert any(row["id"] == created["id"] for row in listed)
    assert listed[0]["review_status"] == "pending_review"

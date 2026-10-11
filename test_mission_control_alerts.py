import sys
import types
from datetime import datetime, timezone

# Isolate alert tests from unrelated optional maritime capture dependencies.
api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules["api_maritime_aviation"] = api_maritime_aviation_stub

from fastapi.testclient import TestClient

import api_server


client = TestClient(api_server.app)


def setup_function() -> None:
    api_server.ALERTS.clear()
    api_server.ALERT_CLIENTS.clear()


def test_distress_alert_is_promoted_to_critical() -> None:
    response = client.post(
        "/alerts",
        json={
            "title": "Urgent marine call",
            "description": "Possible emergency traffic",
            "transcript": "MAYDAY, engine fire onboard",
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["severity"] == "critical"
    assert payload["source"] == "wichita-sdr"


def test_non_distress_alert_defaults_to_warning() -> None:
    response = client.post(
        "/alerts",
        json={
            "title": "Routine channel activity",
            "description": "Regular VHF chatter",
            "signal_type": "marine_vhf",
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["severity"] == "warning"


def test_alert_stores_detected_language_from_payload_or_metadata() -> None:
    explicit = client.post(
        "/alerts",
        json={
            "title": "Voice capture",
            "signal_type": "marine_vhf",
            "language": "IT",
            "source": "wichita-sdr",
        },
    )
    assert explicit.status_code == 200
    assert explicit.json()["language"] == "it"

    fallback = client.post(
        "/alerts",
        json={
            "title": "Voice capture metadata fallback",
            "signal_type": "marine_vhf",
            "metadata": {"transcript_language": "AR"},
            "source": "wichita-sdr",
        },
    )
    assert fallback.status_code == 200
    assert fallback.json()["language"] == "ar"


def test_mission_control_helper_still_posts_when_called_directly(monkeypatch) -> None:
    sent = []

    def fake_post_json(url, payload, headers, timeout):
        sent.append({"url": url, "channel": payload.get("channel")})

    monkeypatch.setenv("MC_CONVERSATION_WEBHOOK_URL", "http://mc.local/conversation")
    monkeypatch.setenv("MC_KANBAN_WEBHOOK_URL", "http://mc.local/kanban")
    monkeypatch.setattr(api_server, "_post_json", fake_post_json)

    record = api_server.AlertRecord(
        id="mc-direct",
        created_at=datetime.now(timezone.utc),
        title="Direct MC test",
        description=None,
        signal_type=api_server.SignalType.UNKNOWN,
        severity=api_server.AlertSeverity.INFO,
        frequency_mhz=None,
        confidence=0.5,
        transcript=None,
        language=None,
        audio_url=None,
        tags=[],
        metadata={},
        source="test",
    )
    api_server._dispatch_alert_to_mission_control(record)
    assert len(sent) == 2


def test_high_stress_alert_does_not_auto_notify(monkeypatch) -> None:
    sent = []

    monkeypatch.setattr(
        api_server,
        "send_stress_alert",
        lambda *a, **k: sent.append(True) or True,
    )
    monkeypatch.setattr(
        api_server,
        "send_discord_alert",
        lambda *a, **k: sent.append(True) or True,
    )

    response = client.post(
        "/alerts",
        json={
            "title": "Voice stress event",
            "transcript": "Breathing heavy and speaking rapidly; requesting help.",
            "metadata": {"stress_score": 83, "trigger": "rapid speech"},
            "frequency_hz": 156800000,
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    assert response.json()["review_status"] == "pending_review"
    assert sent == []

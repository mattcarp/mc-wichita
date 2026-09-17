import sys
import types

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


def test_dispatch_to_mission_control_conversation_and_kanban(monkeypatch) -> None:
    sent = []

    def fake_post_json(url, payload, headers, timeout):
        sent.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout": timeout,
            }
        )

    monkeypatch.setenv("MC_CONVERSATION_WEBHOOK_URL", "http://mc.local/conversation")
    monkeypatch.setenv("MC_KANBAN_WEBHOOK_URL", "http://mc.local/kanban")
    monkeypatch.setenv("MC_WEBHOOK_BEARER_TOKEN", "secret-token")
    monkeypatch.setenv("MC_WEBHOOK_TIMEOUT", "7")
    monkeypatch.setattr(api_server, "_post_json", fake_post_json)

    response = client.post(
        "/alerts",
        json={
            "title": "Signal detected",
            "description": "Test Mission Control routing",
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    assert len(sent) == 2

    first = sent[0]
    second = sent[1]

    assert first["url"] == "http://mc.local/conversation"
    assert first["payload"]["channel"] == "conversation"
    assert first["headers"]["Authorization"] == "Bearer secret-token"
    assert first["timeout"] == 7

    assert second["url"] == "http://mc.local/kanban"
    assert second["payload"]["channel"] == "kanban"
    assert second["headers"]["Authorization"] == "Bearer secret-token"
    assert second["timeout"] == 7


def test_high_stress_alert_triggers_telegram_notification(monkeypatch) -> None:
    sent = []

    def fake_send_stress_alert(stress_score, frequency, transcription, indicators):
        sent.append(
            {
                "stress_score": stress_score,
                "frequency": frequency,
                "transcription": transcription,
                "indicators": indicators,
            }
        )
        return True

    monkeypatch.setattr(api_server, "send_stress_alert", fake_send_stress_alert)

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
    assert len(sent) == 1
    assert sent[0]["stress_score"] == 83
    assert sent[0]["frequency"] == 156800000
    assert "Breathing heavy" in sent[0]["transcription"]
    assert sent[0]["indicators"]["trigger"] == "rapid speech"


def test_high_stress_alert_triggers_discord_notification(monkeypatch) -> None:
    sent = []

    def fake_send_discord_alert(message, stress_score, transcription_preview):
        sent.append(
            {
                "message": message,
                "stress_score": stress_score,
                "transcription_preview": transcription_preview,
            }
        )
        return True

    monkeypatch.setattr(api_server, "send_discord_alert", fake_send_discord_alert)

    response = client.post(
        "/alerts",
        json={
            "title": "Voice stress event",
            "transcript": "Caller is panicking and breathing heavily near harbor.",
            "metadata": {"stress_score": 84},
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0]["stress_score"] == 84
    assert "panicking and breathing heavily" in sent[0]["transcription_preview"]


def test_high_priority_event_triggers_spotify_audio_alert(monkeypatch) -> None:
    sent = []

    def fake_dispatch_spotify_audio_alert(alert, stress_score):
        sent.append({"title": alert.title, "stress_score": stress_score})
        return True

    monkeypatch.setattr(
        api_server, "_dispatch_spotify_audio_alert", fake_dispatch_spotify_audio_alert
    )

    response = client.post(
        "/alerts",
        json={
            "title": "Wichita signal reported near ferry terminal",
            "description": "Priority interception requested.",
            "signal_type": "marine_vhf",
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    assert len(sent) == 1
    assert "Wichita signal" in sent[0]["title"]
    assert sent[0]["stress_score"] is None


def test_routine_alert_does_not_trigger_spotify_audio_alert(monkeypatch) -> None:
    sent = []

    def fake_dispatch_spotify_audio_alert(alert, stress_score):
        sent.append({"title": alert.title, "stress_score": stress_score})
        return True

    monkeypatch.setattr(
        api_server, "_dispatch_spotify_audio_alert", fake_dispatch_spotify_audio_alert
    )

    response = client.post(
        "/alerts",
        json={
            "title": "Routine harbor traffic",
            "description": "Normal channel checks.",
            "signal_type": "marine_vhf",
            "source": "wichita-sdr",
        },
    )

    assert response.status_code == 200
    assert len(sent) == 0

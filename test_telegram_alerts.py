import telegram_alerts


def test_send_alert_posts_expected_payload(monkeypatch) -> None:
    captured = {}

    def fake_post(bot_token, chat_id, text, timeout):
        captured["bot_token"] = bot_token
        captured["chat_id"] = chat_id
        captured["text"] = text
        captured["timeout"] = timeout

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-123")
    monkeypatch.setenv("MATTIE_TELEGRAM_USER_ID", "8508029937")
    monkeypatch.setattr(telegram_alerts, "_post_telegram_message", fake_post)

    success = telegram_alerts.send_alert(
        "High stress detected", 88, "This is a transcription preview."
    )

    assert success is True
    assert captured["bot_token"] == "token-123"
    assert captured["chat_id"] == "8508029937"
    assert "Stress score: 88.0%" in captured["text"]
    assert "Transcription preview: This is a transcription preview." in captured["text"]
    assert "Timestamp:" in captured["text"]


def test_send_test_message_uses_send_alert(monkeypatch) -> None:
    captured = {}

    def fake_send_alert(message, stress_score, transcription_preview):
        captured["message"] = message
        captured["stress_score"] = stress_score
        captured["transcription_preview"] = transcription_preview
        return True

    monkeypatch.setattr(telegram_alerts, "send_alert", fake_send_alert)
    success = telegram_alerts.send_test_message()

    assert success is True
    assert captured["message"] == "Wichita Telegram integration test"
    assert captured["stress_score"] == 71.0

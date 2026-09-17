#!/usr/bin/env python3
"""
Discord alert integration for Wichita.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import urllib.error
import urllib.request
from typing import Optional


DEFAULT_TIMEOUT_SEC = 10


def _normalize_stress_score(stress_score: float | int) -> float:
    score = float(stress_score)
    if 0.0 <= score <= 1.0:
        return round(score * 100.0, 1)
    return round(score, 1)


def _preview_text(text: Optional[str], max_chars: int = 220) -> str:
    value = (text or "").strip()
    if not value:
        return "N/A"
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _format_alert_text(
    message: str, stress_score: float | int, transcription_preview: Optional[str]
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    score = _normalize_stress_score(stress_score)
    preview = _preview_text(transcription_preview)
    return (
        "WICHITA HIGH-STRESS ALERT\n"
        f"Message: {message.strip() or 'High-stress voice event'}\n"
        f"Stress score: {score:.1f}%\n"
        f"Transcription preview: {preview}\n"
        f"Timestamp: {timestamp}"
    )


def _post_discord_message(
    webhook_url: str, content: str, timeout: int = DEFAULT_TIMEOUT_SEC
) -> None:
    body = json.dumps({"content": content}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def send_alert(
    message: str, stress_score: float | int, transcription_preview: Optional[str]
) -> bool:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return False

    timeout = int(os.getenv("DISCORD_ALERT_TIMEOUT", str(DEFAULT_TIMEOUT_SEC)))
    alert_text = _format_alert_text(message, stress_score, transcription_preview)
    try:
        _post_discord_message(webhook_url, alert_text, timeout=timeout)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return False


def send_test_message() -> bool:
    return send_alert(
        message="Wichita Discord integration test",
        stress_score=71.0,
        transcription_preview="Test message from Wichita high-stress alert pipeline.",
    )


if __name__ == "__main__":
    success = send_test_message()
    print("Discord test sent" if success else "Discord test failed")

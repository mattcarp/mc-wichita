#!/usr/bin/env python3
"""Alert dispatch utilities for high-stress voice detections."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional
import json
import os
import urllib.error
import urllib.request

DEFAULT_CHAT_ID = "8508029937"
DEFAULT_TIMEOUT_SEC = 10
TOKEN_FILE_PATH = Path("/etc/telegram_bot_token")


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


def _read_bot_token_from_file(path: Path = TOKEN_FILE_PATH) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None
    return value or None


def _resolve_bot_token() -> Optional[str]:
    return os.getenv("TELEGRAM_BOT_TOKEN") or _read_bot_token_from_file()


def _format_indicators(indicators: Any) -> str:
    if indicators is None:
        return "N/A"

    if isinstance(indicators, Mapping):
        parts = []
        for key, value in indicators.items():
            parts.append(f"{key}={value}")
        return ", ".join(parts) if parts else "N/A"

    if isinstance(indicators, (list, tuple, set)):
        items = [str(item).strip() for item in indicators if str(item).strip()]
        return ", ".join(items) if items else "N/A"

    return str(indicators).strip() or "N/A"


def _format_frequency(frequency: Any) -> str:
    if frequency is None:
        return "unknown"

    try:
        value = float(frequency)
    except (TypeError, ValueError):
        return str(frequency)

    if value > 1e6:
        return f"{value / 1e6:.3f} MHz"
    if value > 1e3:
        return f"{value / 1e3:.1f} kHz"
    return f"{value:.1f} Hz"


def _format_alert_text(
    stress_score: float | int,
    frequency: Any,
    transcription: Optional[str],
    indicators: Any,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        "WICHITA HIGH-STRESS ALERT\n"
        f"Stress score: {_normalize_stress_score(stress_score):.1f}%\n"
        f"Frequency: {_format_frequency(frequency)}\n"
        f"Indicators: {_format_indicators(indicators)}\n"
        f"Transcription preview: {_preview_text(transcription)}\n"
        f"Timestamp: {timestamp}"
    )


def _post_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> None:
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def send_stress_alert(
    stress_score: float | int,
    frequency: Any,
    transcription: Optional[str],
    indicators: Any,
) -> bool:
    """Send a high-stress Telegram alert to Mattie."""
    bot_token = _resolve_bot_token()
    if not bot_token:
        return False

    chat_id = os.getenv("TELEGRAM_CHAT_ID", DEFAULT_CHAT_ID)
    timeout = int(os.getenv("TELEGRAM_ALERT_TIMEOUT", str(DEFAULT_TIMEOUT_SEC)))
    text = _format_alert_text(stress_score, frequency, transcription, indicators)

    try:
        _post_telegram_message(bot_token, chat_id, text, timeout=timeout)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return False

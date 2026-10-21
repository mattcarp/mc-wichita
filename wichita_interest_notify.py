"""Phone ping for boats of interest (reuses Telegram stress-alert channel)."""

from __future__ import annotations

import os
from typing import Optional

from alert_dispatcher import _post_telegram_message, _read_bot_token_from_file, DEFAULT_CHAT_ID, DEFAULT_TIMEOUT_SEC


def _resolve_bot_token() -> Optional[str]:
    return os.getenv("TELEGRAM_BOT_TOKEN") or _read_bot_token_from_file()


def notify_boat_of_interest_heard(title: str, position: str, speed: str, last_heard_malta: str) -> bool:
    """Send a plain-text Telegram ping when a boat of interest is heard."""
    bot_token = _resolve_bot_token()
    if not bot_token:
        return False
    chat_id = os.getenv("TELEGRAM_CHAT_ID", os.getenv("MATTIE_TELEGRAM_USER_ID", DEFAULT_CHAT_ID))
    timeout = int(os.getenv("TELEGRAM_ALERT_TIMEOUT", str(DEFAULT_TIMEOUT_SEC)))
    text = (
        "WICHITA BOAT OF INTEREST\n"
        f"{title} heard\n"
        f"Position: {position}\n"
        f"Speed: {speed}\n"
        f"Last heard: {last_heard_malta} (Europe/Malta)"
    )
    try:
        _post_telegram_message(bot_token, chat_id, text, timeout=timeout)
        return True
    except Exception:
        return False

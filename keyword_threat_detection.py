#!/usr/bin/env python3
"""Keyword and threat detection for transcribed RF transmissions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional
import json

ALERTS_FILE = Path("alerts.json")

DISTRESS_KEYWORDS = {
    "en": {
        "mayday": 95,
        "sos": 85,
        "distress": 82,
        "help": 80,
    },
    "it": {
        "soccorso": 86,
        "aiuto": 82,
    },
    "mt": {
        "ajjut": 84,
    },
    "ar": {
        "نجدة": 88,
    },
}

CRIMINAL_KEYWORDS = {
    "en": {
        "pan-pan": 65,
        "pan pan": 65,
        "meet at": 50,
        "drop the": 48,
        "shipment": 45,
        "pickup": 44,
        "handoff": 46,
        "deliver": 42,
    },
    "it": {
        "incontro": 44,
        "consegna": 46,
    },
    "mt": {
        "laqgha": 44,
        "kunsinna": 46,
    },
    "ar": {
        "شحنة": 45,
        "تسليم": 46,
    },
}

SUSPICIOUS_KEYWORDS = {
    "en": {
        "tonight": 28,
        "no questions": 30,
        "quietly": 24,
    },
    "it": {
        "stanotte": 24,
    },
    "mt": {
        "illejla": 24,
    },
    "ar": {
        "الليلة": 24,
    },
}


def _languages_for_lookup(language: Optional[str]) -> Iterable[str]:
    normalized = (language or "").strip().lower()
    seen = set()
    for code in (normalized, "en", "mt", "it", "ar"):
        if code and code not in seen:
            seen.add(code)
            yield code


def _best_match(text: str, language: str) -> tuple[Optional[str], int]:
    haystack = (text or "").lower()
    best_keyword = None
    best_score = 0

    def _scan(groups: Dict[str, Dict[str, int]]) -> None:
        nonlocal best_keyword, best_score
        for code in _languages_for_lookup(language):
            for keyword, score in groups.get(code, {}).items():
                if keyword in haystack and score > best_score:
                    best_keyword = keyword
                    best_score = score

    _scan(DISTRESS_KEYWORDS)
    _scan(CRIMINAL_KEYWORDS)
    _scan(SUSPICIOUS_KEYWORDS)
    return best_keyword, int(best_score)


def _append_alert(alert: Dict[str, object]) -> None:
    existing = []
    if ALERTS_FILE.exists():
        try:
            payload = json.loads(ALERTS_FILE.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                existing = payload
        except Exception:
            existing = []

    existing.append(alert)
    ALERTS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_threats(transcription_dict: dict, frequency_hz: float | None = None) -> dict:
    text = str((transcription_dict or {}).get("text", "")).strip()
    language = str((transcription_dict or {}).get("language", "unknown") or "unknown").lower()

    keyword, threat_score = _best_match(text, language)
    alert = threat_score > 0

    result = {
        "keyword": keyword,
        "threat_score": int(threat_score),
        "language": language,
        "alert": alert,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frequency_hz": float(frequency_hz) if frequency_hz is not None else None,
    }

    if alert:
        _append_alert(result)

    return result


__all__ = ["ALERTS_FILE", "detect_threats"]

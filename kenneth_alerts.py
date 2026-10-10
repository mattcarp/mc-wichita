#!/usr/bin/env python3
"""
Kenneth Alert System — issue #24

Sends Telegram alerts to Mattie when Kenneth detects:
- High voice stress (>70% threshold)
- Implicit distress patterns (breathing, alarms, crying, slurred speech)
- MAYDAY / SOS / distress keywords regardless of stress score
- CRITICAL compound triggers (alarm + stress, etc.)

Thresholds:
  <40%   → log only
  40-70% → log + store
  70-90% → Telegram alert
  >90%   → Telegram alert + CRITICAL flag
  MAYDAY/SOS → Telegram alert regardless

Usage (standalone test):
    python kenneth_alerts.py --test

Integration (from voice_hunting_scanner.py):
    from kenneth_alerts import maybe_alert
    maybe_alert(channel_id, freq_mhz, stress_score, transcript, implicit_result)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import requests

# Keyword detection module
try:
    from kenneth_keywords import analyze_transcript as kw_analyze, keyword_alert_level
    HAS_KEYWORDS = True
except ImportError:
    HAS_KEYWORDS = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger('kenneth-alerts')

# ── Config ────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get(
    'TELEGRAM_BOT_TOKEN',
    '8590059603:AAFX0sPodqPHd6SltnqmExUZG4RTaXkL35Q'  # Claudette bot
)
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8508029937')  # Mattie

# Stress thresholds
THRESHOLD_LOG_ONLY    = 40   # below this: log only
THRESHOLD_STORE       = 40   # 40-70: log + store
THRESHOLD_ALERT       = 70   # 70+: Telegram alert
THRESHOLD_CRITICAL    = 90   # 90+: CRITICAL label

# Distress keywords (any triggers alert regardless of stress score)
DISTRESS_KEYWORDS = [
    # English
    'mayday', 'sos', 'pan pan', 'pan-pan', 'distress', 'sinking', 'abandon ship',
    'man overboard', 'emergency', 'help us', 'we are sinking', 'taking on water',
    # Maltese
    'għajnuna', 'inqerq', 'emerġenza', 'se negħrqu',
    # Italian
    'mayday', 'sos', 'soccorso', 'emergenza', 'affondamento', 'aiuto',
    # Arabic
    'نجدة', 'إنقاذ', 'طوارئ',
]

# Implicit distress alert levels that trigger Telegram
IMPLICIT_ALERT_LEVELS = {'MEDIUM', 'HIGH', 'CRITICAL'}

# Rate limiting: don't spam per channel
_last_alert: Dict[str, float] = {}
ALERT_COOLDOWN_S = 300  # 5 minutes per channel


def _rate_limited(channel_id: str) -> bool:
    now = time.time()
    last = _last_alert.get(channel_id, 0)
    if now - last < ALERT_COOLDOWN_S:
        return True
    _last_alert[channel_id] = now
    return False


def _contains_keyword(transcript: str, stress_score: float = 0.0) -> Optional[str]:
    """Return the highest-alert matched keyword using kenneth_keywords module."""
    if HAS_KEYWORDS and transcript:
        level, phrase = keyword_alert_level(transcript, stress_score=stress_score)
        if level != "NONE":
            return phrase
    # Fallback: basic list
    lower = transcript.lower()
    for kw in DISTRESS_KEYWORDS:
        if kw in lower:
            return kw
    return None


def send_telegram(message: str, parse_mode: str = 'Markdown') -> bool:
    """Send a Telegram message to Mattie. Returns True on success."""
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': parse_mode,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f'Telegram alert sent (chat_id={TELEGRAM_CHAT_ID})')
            return True
        else:
            logger.error(f'Telegram send failed: {resp.status_code} {resp.text[:200]}')
            return False
    except Exception as e:
        logger.error(f'Telegram send exception: {e}')
        return False


def format_alert(
    channel_id: str,
    freq_mhz: float,
    stress_score: float,
    transcript: str,
    implicit_result: Optional[Dict] = None,
    keyword_match: Optional[str] = None,
    is_critical: bool = False,
) -> str:
    """Format a Kenneth alert message for Telegram."""
    now = datetime.now(timezone.utc).strftime('%H:%M:%S')
    stress_pct = int(stress_score * 100)
    
    # Header
    icon = '🔴' if is_critical else '🟠' if stress_pct >= 70 else '🟡'
    label = 'CRITICAL' if is_critical else 'ALERT'
    lines = [
        f'{icon} *KENNETH {label}*',
        '━━━━━━━━━━━━━━━',
        f'📡 *Frequency:* {freq_mhz:.3f} MHz ({channel_id})',
        f'⏰ *Time:* {now} UTC',
        f'🔥 *Stress:* {stress_pct}%',
    ]
    
    # Keyword hit
    if keyword_match:
        lines.append(f'⚠️ *Keyword:* ' + chr(96) + keyword_match + chr(96))
    
    # Implicit distress
    if implicit_result and implicit_result.get('triggers'):
        triggers = ', '.join(implicit_result['triggers'])
        imp_level = implicit_result.get('alert_level', '')
        lines.append(f'🧠 *Implicit:* [{imp_level}] {triggers}')
    
    # Transcript
    if transcript and transcript.strip():
        preview = transcript.strip()[:200]
        lines.append(f'📝 _{preview}_')
    
    lines.append('━━━━━━━━━━━━━━━')
    lines.append('_Kenneth RF Sentinel · Xagħra_')
    
    return '\n'.join(lines)


def maybe_alert(
    channel_id: str,
    freq_mhz: float,
    stress_score: float,          # 0.0–1.0
    transcript: str = '',
    implicit_result: Optional[Dict] = None,
) -> Dict:
    """
    Core entry point. Evaluate whether to send an alert and do so if warranted.
    Returns a dict describing what action was taken.
    """
    stress_pct = stress_score * 100
    keyword_match = _contains_keyword(transcript, stress_score=stress_score)
    implicit_level = (implicit_result or {}).get('alert_level', 'NONE')
    implicit_triggers = (implicit_result or {}).get('triggers', [])

    # Determine if we should alert
    should_alert = False
    reason = 'below_threshold'

    if keyword_match:
        should_alert = True
        reason = f'keyword:{keyword_match}'
    elif stress_pct >= THRESHOLD_ALERT:
        should_alert = True
        reason = f'stress:{stress_pct:.0f}%'
    elif implicit_level in IMPLICIT_ALERT_LEVELS:
        should_alert = True
        reason = f'implicit:{implicit_level}'

    is_critical = (
        stress_pct >= THRESHOLD_CRITICAL or
        implicit_level == 'CRITICAL' or
        keyword_match in ['mayday', 'sos', 'pan pan', 'pan-pan']
    )

    action = {
        'channel_id': channel_id,
        'freq_mhz': freq_mhz,
        'stress_pct': round(stress_pct, 1),
        'keyword': keyword_match,
        'implicit_level': implicit_level,
        'should_alert': should_alert,
        'reason': reason,
        'is_critical': is_critical,
        'sent': False,
        'rate_limited': False,
    }

    if not should_alert:
        logger.debug(f'No alert for {channel_id} — {reason}')
        return action

    # Rate limit check
    if _rate_limited(channel_id):
        logger.info(f'Alert rate-limited for {channel_id} (cooldown {ALERT_COOLDOWN_S}s)')
        action['rate_limited'] = True
        return action

    # Format and send
    message = format_alert(
        channel_id=channel_id,
        freq_mhz=freq_mhz,
        stress_score=stress_score,
        transcript=transcript,
        implicit_result=implicit_result,
        keyword_match=keyword_match,
        is_critical=is_critical,
    )

    action['sent'] = send_telegram(message)
    if action['sent']:
        logger.warning(
            f'🚨 Alert sent [{"CRITICAL" if is_critical else "ALERT"}] '
            f'{channel_id} {freq_mhz:.3f}MHz stress={stress_pct:.0f}% reason={reason}'
        )
    return action


# ── CLI test ──────────────────────────────────────────────────────────────────

def test_alert():
    """Send a test alert to verify end-to-end delivery."""
    logger.info('Sending test alert to Mattie...')
    result = maybe_alert(
        channel_id='CH16',
        freq_mhz=156.800,
        stress_score=0.84,
        transcript='mayday mayday this is MV test vessel we are taking on water',
        implicit_result={
            'alert_level': 'HIGH',
            'triggers': ['background_alarm', 'slurred_speech'],
        },
    )
    print(json.dumps(result, indent=2))
    return result['sent']


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Kenneth Alert System')
    parser.add_argument('--test', action='store_true', help='Send a test alert')
    parser.add_argument('--channel-id', default='CH16')
    parser.add_argument('--freq', type=float, default=156.800)
    parser.add_argument('--stress', type=float, default=0.84)
    parser.add_argument('--transcript', default='')
    args = parser.parse_args()

    if args.test:
        ok = test_alert()
        exit(0 if ok else 1)
    else:
        result = maybe_alert(args.channel_id, args.freq, args.stress, args.transcript)
        print(json.dumps(result, indent=2))

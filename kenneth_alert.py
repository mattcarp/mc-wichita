#!/usr/bin/env python3
"""
Kenneth Alert System
Sends stress/distress alerts to Mattie via OpenClaw system events.
Thresholds:
  <40%     → log only
  40-70%   → log + store
  70-90%   → alert (HIGH)
  >90%     → alert (CRITICAL)
  MAYDAY/SOS/PAN-PAN in transcript → always alert regardless of score
"""
import subprocess
import json
import os
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

MATTIE_TELEGRAM_ID = "8508029937"

MAYDAY_KEYWORDS = re.compile(
    r'\b(mayday|pan.?pan|sos|emergency|distress|sinking|fire on board|man overboard|abandon ship)\b',
    re.IGNORECASE
)

ALERT_THRESHOLD = 70       # % stress → send alert
CRITICAL_THRESHOLD = 90    # % stress → CRITICAL


@dataclass
class KennethEvent:
    frequency_mhz: float
    stress_score: int          # 0-100
    alert_level: str           # LOW / MEDIUM / HIGH / CRITICAL
    transcript: str
    timestamp: str
    indicators: list
    audio_path: Optional[str] = None
    channel_name: Optional[str] = None  # e.g. "CH16 Emergency", "Malta Approach"
    ais_info: Optional[str] = None


def has_mayday(transcript: str) -> bool:
    return bool(MAYDAY_KEYWORDS.search(transcript))


def should_alert(event: KennethEvent) -> bool:
    """Return True if this event warrants an immediate alert."""
    if has_mayday(event.transcript):
        return True
    return event.stress_score >= ALERT_THRESHOLD


def format_alert(event: KennethEvent) -> str:
    """Format a human-readable alert message."""
    mayday = has_mayday(event.transcript)
    
    level_emoji = {
        "LOW": "🟢",
        "MEDIUM": "🟡",
        "HIGH": "🔴",
        "CRITICAL": "🚨",
    }.get(event.alert_level, "⚠️")
    
    header = "🚨 KENNETH ALERT — MAYDAY DETECTED" if mayday else f"🚨 KENNETH ALERT — {event.alert_level}"
    
    lines = [
        header,
        "━━━━━━━━━━━━━━━",
        f"📡 Frequency: {event.frequency_mhz:.3f} MHz" + (f" ({event.channel_name})" if event.channel_name else ""),
        f"⏰ Time: {event.timestamp} UTC",
        f"{level_emoji} Stress: {event.stress_score}%",
    ]
    
    if event.indicators:
        lines.append(f"🔍 Indicators: {', '.join(event.indicators)}")
    
    if event.transcript and event.transcript.strip():
        transcript_preview = event.transcript[:300].strip()
        lines.append(f"📝 Transcript: \"{transcript_preview}\"")
    
    if event.ais_info:
        lines.append(f"🗺 AIS: {event.ais_info}")
    
    lines.append("━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def send_alert(event: KennethEvent, dry_run: bool = False) -> bool:
    """
    Send alert via openclaw system event.
    Returns True on success.
    """
    if not should_alert(event):
        return False
    
    message = format_alert(event)
    
    if dry_run:
        print("[DRY RUN] Would send:")
        print(message)
        return True
    
    try:
        result = subprocess.run(
            ["openclaw", "system", "event", "--mode", "now", "--text", message],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"[kenneth_alert] Alert sent: {event.alert_level} @ {event.frequency_mhz} MHz")
            return True
        else:
            print(f"[kenneth_alert] Alert failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"[kenneth_alert] Alert exception: {e}")
        return False


def process_stress_result(stress_result: dict, frequency_mhz: float = 0.0,
                           transcript: str = "", channel_name: Optional[str] = None,
                           ais_info: Optional[str] = None, dry_run: bool = False) -> Optional[bool]:
    """
    Convenience wrapper: takes a StressResult dict (from stress_scorer.py)
    and sends an alert if thresholds are met.
    Returns True if alert sent, False if below threshold, None if error.
    """
    score = stress_result.get("stress_score", 0)
    level = stress_result.get("alert_level", "LOW")
    indicators = stress_result.get("indicators", [])
    timestamp = stress_result.get("timestamp", datetime.now(timezone.utc).strftime("%H:%M:%S"))
    
    event = KennethEvent(
        frequency_mhz=frequency_mhz,
        stress_score=score,
        alert_level=level,
        transcript=transcript,
        timestamp=timestamp,
        indicators=indicators,
        channel_name=channel_name,
        ais_info=ais_info,
    )
    
    if not should_alert(event):
        action = "log+store" if score >= 40 else "log only"
        print(f"[kenneth_alert] Score {score}% ({level}) — {action}, no alert sent")
        return False
    
    return send_alert(event, dry_run=dry_run)


if __name__ == "__main__":
    import sys
    
    # Quick test / manual alert
    dry = "--dry-run" in sys.argv
    
    # Demo: simulate a HIGH stress event on CH16
    test_event = KennethEvent(
        frequency_mhz=156.800,
        stress_score=84,
        alert_level="HIGH",
        transcript="vessel in distress please respond this is mv gozo star",
        timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        indicators=["elevated_pitch", "pitch_instability", "high_speech_rate"],
        channel_name="CH16 Emergency",
        ais_info="MV Gozo Star (MMSI 215123456) — last pos: 36.012°N 14.341°E",
    )
    
    print(format_alert(test_event))
    print()
    
    if "--send" in sys.argv:
        result = send_alert(test_event, dry_run=dry)
        print(f"Alert sent: {result}")

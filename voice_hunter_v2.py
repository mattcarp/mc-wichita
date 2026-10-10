#!/usr/bin/env python3
"""
Kenneth Voice Hunter v2 — Properly calibrated for SDRplay RSPdx-R2
Uses two-stage detection: IQ signal detection → FM demod → voice analysis
No more false positives on noise.
"""

import time
import numpy as np
import soundfile as sf

# Kenneth alert + implicit distress integration
try:
    from kenneth_alerts import maybe_alert
    from implicit_distress_detector import analyze_audio as implicit_analyze
    HAS_ALERTS = True
except ImportError as e:
    HAS_ALERTS = False
    import logging as _log
    _log.getLogger('voice-hunter').warning(f'Alerts/implicit disabled: {e}')
from pathlib import Path
from datetime import datetime, timedelta
import json
import logging
import sys

from sdr_capture import capture_iq, is_device_available
from rf_signal_detector import full_detection_pipeline, fm_demodulate, am_demodulate

# Optional: demucs vocal filter + Canary transcription
try:
    from demucs_filter import filter_vocals
    HAS_DEMUCS = True
except ImportError:
    HAS_DEMUCS = False
    
try:
    from canary_transcriber import transcribe as canary_transcribe, is_available as canary_available
    HAS_CANARY = canary_available()
except ImportError:
    HAS_CANARY = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Malta-relevant frequencies
FREQUENCIES = {
    # Maritime — high priority
    'CH16': {'freq': 156.800e6, 'name': 'Emergency/Calling', 'priority': 3, 'type': 'maritime'},
    'CH13': {'freq': 156.650e6, 'name': 'Bridge-to-Bridge', 'priority': 3, 'type': 'maritime'},
    'CH09': {'freq': 156.450e6, 'name': 'Calling', 'priority': 2, 'type': 'maritime'},
    'CH22A': {'freq': 157.100e6, 'name': 'Coast Guard', 'priority': 2, 'type': 'maritime'},
    'CH12': {'freq': 156.600e6, 'name': 'Valletta VTS', 'priority': 2, 'type': 'maritime'},
    'CH06': {'freq': 156.300e6, 'name': 'Ship Safety', 'priority': 1, 'type': 'maritime'},
    'CH08': {'freq': 156.400e6, 'name': 'Commercial', 'priority': 1, 'type': 'maritime'},
    'CH10': {'freq': 156.500e6, 'name': 'Commercial', 'priority': 1, 'type': 'maritime'},
    'CH68': {'freq': 156.425e6, 'name': 'Non-commercial', 'priority': 1, 'type': 'maritime'},
    'CH72': {'freq': 156.625e6, 'name': 'Non-commercial', 'priority': 1, 'type': 'maritime'},
    
    # Aviation
    'LUQA_TWR': {'freq': 118.100e6, 'name': 'Malta Tower', 'priority': 2, 'type': 'aviation'},
    'LUQA_APP': {'freq': 119.450e6, 'name': 'Malta Approach', 'priority': 2, 'type': 'aviation'},
    'LUQA_GND': {'freq': 121.700e6, 'name': 'Malta Ground', 'priority': 1, 'type': 'aviation'},
    'GUARD': {'freq': 121.500e6, 'name': 'Emergency Guard', 'priority': 3, 'type': 'aviation'},
}


class VoiceHunterV2:
    def __init__(self, output_dir='rf_captures'):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path(output_dir) / f'hunt_{self.session_id}'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Add file logging
        fh = logging.FileHandler(self.output_dir / 'hunt.log')
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(fh)
        
        self.stats = {
            'scans': 0,
            'signals': 0,
            'voices': 0,
            'captures': 0,
            'by_type': {'maritime': 0, 'aviation': 0},
        }
        self.captures = []
    
    def scan_frequency(self, channel_id, info):
        """Scan one frequency. Returns True if voice detected."""
        freq = info['freq']
        freq_mhz = freq / 1e6
        
        logger.info(f"📡 {channel_id} ({info['name']}) — {freq_mhz:.3f} MHz")
        
        # Quick 3-second IQ capture
        iq = capture_iq(freq, duration_seconds=3.0, gain=30)
        if iq is None:
            logger.warning(f"   ⚠️ Capture failed")
            return False
        
        self.stats['scans'] += 1
        
        # Two-stage detection
        modulation = "am" if info.get("type") == "aviation" else "fm"
        has_voice, details = full_detection_pipeline(iq, modulation=modulation)
        
        dr = details.get('iq_dynamic_range_dB', 0)
        sf_val = details.get('spectral_flatness', 1)
        reason = details.get("rejection_reason", "")
        
        if reason == 'no_signal':
            logger.info(f"   — noise (DR={dr:.1f}dB, flat={sf_val:.3f})")
            return False
        
        if reason == 'signal_but_no_voice':
            self.stats['signals'] += 1
            vr = details.get('voice_ratio', 0)
            logger.info(f"   📶 Signal! (DR={dr:.1f}dB) but no voice (VR={vr:.1%})")
            return False
        
        # VOICE DETECTED
        self.stats['voices'] += 1
        self.stats['by_type'][info['type']] += 1
        voice_score = details.get('voice_score', 0)
        logger.info(f"   🎤 VOICE! score={voice_score:.2f} DR={dr:.1f}dB")
        
        # Extended capture
        return self.extended_capture(channel_id, info, details)
    
    def extended_capture(self, channel_id, info, initial_details):
        """Capture extended audio when voice is found."""
        freq = info['freq']
        logger.info(f"   🔴 Extended capture (15s)...")
        
        iq = capture_iq(freq, duration_seconds=15.0, gain=30)
        if iq is None:
            logger.warning(f"   ⚠️ Extended capture failed")
            return False
        
        modulation = "am" if info.get("type") == "aviation" else "fm"
        audio = am_demodulate(iq) if modulation == "am" else fm_demodulate(iq)
        
        # Save WAV
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"VOICE_{channel_id}_{info['freq']/1e6:.3f}MHz_{ts}.wav"
        filepath = self.output_dir / filename
        sf.write(str(filepath), audio, 48000)
        
        self.stats['captures'] += 1
        
        capture_info = {
            'file': filename,
            'channel': channel_id,
            'name': info['name'],
            'freq_mhz': info['freq'] / 1e6,
            'type': info['type'],
            'timestamp': ts,
            'voice_score': initial_details.get('voice_score', 0),
            'iq_dynamic_range_dB': initial_details.get('iq_dynamic_range_dB', 0),
        }
        self.captures.append(capture_info)
        
        logger.info(f"   ✅ Saved: {filename}")

        # Run implicit distress analysis + alert
        if HAS_ALERTS:
            try:
                implicit = implicit_analyze(
                    str(filepath),
                    channel_id=channel_id,
                    stress_score=initial_details.get('voice_score', 0),
                )
                maybe_alert(
                    channel_id=channel_id,
                    freq_mhz=info['freq'] / 1e6,
                    stress_score=initial_details.get('voice_score', 0),
                    transcript='',  # whisper transcription future work
                    implicit_result=implicit,
                )
            except Exception as _ae:
                logger.warning(f'Alert/implicit error: {_ae}')

        return True
    
    def build_scan_order(self):
        """Build frequency scan order weighted by priority."""
        order = []
        for ch_id, info in FREQUENCIES.items():
            for _ in range(info['priority']):
                order.append((ch_id, info))
        return order
    
    def run(self, duration_minutes=5):
        """Run the hunt."""
        logger.info(f"🎯 Kenneth Voice Hunter v2")
        logger.info(f"   Session: {self.session_id}")
        logger.info(f"   Duration: {duration_minutes} min")
        logger.info(f"   Frequencies: {len(FREQUENCIES)}")
        logger.info(f"   Output: {self.output_dir}")
        
        if not is_device_available():
            logger.error("❌ No SDRplay device found!")
            return
        
        logger.info(f"   SDR: SDRplay RSPdx-R2 ✅")
        logger.info("=" * 60)
        
        scan_order = self.build_scan_order()
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        scan_idx = 0
        
        try:
            while datetime.now() < end_time:
                ch_id, info = scan_order[scan_idx % len(scan_order)]
                self.scan_frequency(ch_id, info)
                scan_idx += 1
                time.sleep(1)  # Brief pause between scans
        except KeyboardInterrupt:
            logger.info("\n👋 Interrupted")
        
        self.print_summary()
        self.save_results()
    
    def print_summary(self):
        elapsed = datetime.now() - datetime.strptime(self.session_id, '%Y%m%d_%H%M%S')
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 HUNT SUMMARY ({elapsed})")
        logger.info(f"   Scans: {self.stats['scans']}")
        logger.info(f"   Signals found: {self.stats['signals']}")
        logger.info(f"   Voices found: {self.stats['voices']}")
        logger.info(f"   Captures saved: {self.stats['captures']}")
        logger.info(f"   Maritime: {self.stats['by_type']['maritime']}")
        logger.info(f"   Aviation: {self.stats['by_type']['aviation']}")
    
    def save_results(self):
        summary = {
            'session': self.session_id,
            'stats': self.stats,
            'captures': self.captures,
        }
        path = self.output_dir / 'summary.json'
        with open(path, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"📁 Results: {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Kenneth Voice Hunter v2')
    parser.add_argument('--minutes', type=int, default=5, help='Duration (default 5)')
    args = parser.parse_args()
    
    hunter = VoiceHunterV2()
    hunter.run(duration_minutes=args.minutes)


if __name__ == '__main__':
    main()

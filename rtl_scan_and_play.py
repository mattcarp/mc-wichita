#!/usr/bin/env python3
"""
Real RTL-SDR frequency scanner with playback
Captures audio from each frequency and plays it for evaluation
"""

import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone

print("🎯 Real RTL-SDR Voice Frequency Scanner")
print("=" * 60)

# FM Radio frequencies that likely have voice/music
frequencies = [
    {"freq": "88.5", "name": "FM Radio Station", "gain": 30},
    {"freq": "91.1", "name": "FM Radio Station", "gain": 30},
    {"freq": "93.7", "name": "FM Radio Station", "gain": 30},
    {"freq": "95.1", "name": "FM Radio Station", "gain": 30},
    {"freq": "97.5", "name": "FM Radio Station", "gain": 30},
    {"freq": "100.2", "name": "FM Radio Station", "gain": 30},
    {"freq": "103.5", "name": "FM Radio Station", "gain": 30},
    {"freq": "105.7", "name": "FM Radio Station", "gain": 30},
]

# Create capture directory
capture_dir = Path("rtl_voice_captures")
capture_dir.mkdir(exist_ok=True)

for i, freq_info in enumerate(frequencies):
    freq_mhz = freq_info["freq"]
    name = freq_info["name"]
    gain = freq_info["gain"]
    
    print(f"\n[{i+1}/{len(frequencies)}] Capturing {freq_mhz} MHz - {name}")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = capture_dir / f"RTL_CAPTURE_{freq_mhz}MHz_{timestamp}.wav"
    
    # Use rtl_fm to capture and sox to convert to WAV
    print(f"   📡 Tuning to {freq_mhz} MHz...")
    print(f"   ⏱️  Recording for 5 seconds...")
    
    # RTL-SDR capture command
    cmd = f"timeout 5 rtl_fm -f {freq_mhz}M -M wbfm -s 200000 -r 48000 -g {gain} - | sox -t raw -r 48000 -e signed -b 16 -c 1 - {output_file}"
    
    try:
        subprocess.run(cmd, shell=True, capture_output=True, timeout=7)
        
        if output_file.exists():
            print(f"   ✅ Captured: {output_file.name}")
            print(f"   🔊 Playing capture...")
            
            # Play the captured audio
            subprocess.run(f"afplay {output_file}", shell=True)
            
            print(f"   ⏸️  Is this good? (Has voice/music content?)")
            print(f"   Waiting for your feedback...")
            break  # Wait for user feedback before continuing
        else:
            print(f"   ❌ Capture failed")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n📻 Tell me if this capture has good voice/music content!")
print("I'll continue scanning based on your feedback.")

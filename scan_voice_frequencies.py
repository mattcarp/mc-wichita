#!/usr/bin/env python3
"""
Scan common voice frequencies for better examples
"""

import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone

print("🎯 RF Voice Frequency Scanner")
print("=" * 60)

# Common voice frequencies to scan
frequencies = [
    {"freq": "88.5MHz", "name": "FM Radio (Music/Talk)", "duration": 10},
    {"freq": "91.1MHz", "name": "FM Radio Station", "duration": 10},
    {"freq": "93.7MHz", "name": "FM Radio Station", "duration": 10},
    {"freq": "95.1MHz", "name": "FM Radio Station", "duration": 10},
    {"freq": "97.5MHz", "name": "FM Radio Station", "duration": 10},
    {"freq": "100.2MHz", "name": "FM Radio Station", "duration": 10},
    {"freq": "103.5MHz", "name": "FM Radio Station", "duration": 10},
    {"freq": "156.800MHz", "name": "Maritime CH16 Emergency", "duration": 15},
    {"freq": "156.450MHz", "name": "Maritime CH09 Calling", "duration": 15},
    {"freq": "121.500MHz", "name": "Aviation Emergency", "duration": 15},
    {"freq": "118.100MHz", "name": "Airport Tower", "duration": 15},
]

print(f"Scanning {len(frequencies)} frequencies for voice content...")
print("This will help us find clear voice samples for QWEN3 ASR testing\n")

# Create captures directory
capture_dir = Path("voice_scan_captures")
capture_dir.mkdir(exist_ok=True)

captured_files = []

for i, freq_info in enumerate(frequencies[:5]):  # Start with first 5
    freq = freq_info["freq"]
    name = freq_info["name"]
    duration = freq_info["duration"]
    
    print(f"\n[{i+1}/{len(frequencies[:5])}] Scanning {freq} - {name}")
    print(f"   Duration: {duration} seconds")
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = capture_dir / f"SCAN_{freq.replace('.', '_')}_{timestamp}.wav"
    
    # Using rtl_fm to capture FM frequencies
    # Adjust for your SDR hardware (SDRplay or RTL-SDR)
    cmd = [
        "rtl_fm",
        "-f", freq.replace("MHz", "M"),
        "-M", "wbfm",  # Wide FM for broadcast
        "-s", "200000",  # Sample rate
        "-r", "48000",   # Output rate
        output_file.stem + ".raw"
    ]
    
    print(f"   Command: {' '.join(cmd)}")
    print(f"   Capturing...")
    
    # Note: This is a placeholder - actual capture would require SDR hardware
    print(f"   ⚠️  SDR hardware required for actual capture")
    print(f"   Would save to: {output_file}")
    
    captured_files.append(str(output_file))
    time.sleep(1)  # Pause between scans

print(f"\n✅ Scan complete!")
print(f"Planned captures: {len(captured_files)}")
print("\nFor actual scanning, ensure:")
print("1. SDRplay or RTL-SDR is connected")
print("2. Antenna is properly positioned")
print("3. Use appropriate capture software for your hardware")

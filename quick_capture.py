#!/usr/bin/env python3
"""
Simple RTL-SDR capture and immediate playback
"""

import subprocess
import time
from datetime import datetime, timezone

freq = "88.5"
print(f"📡 Capturing FM Radio at {freq} MHz for 5 seconds...")

timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
output_file = f"capture_{freq}MHz_{timestamp}.wav"

# Direct rtl_fm capture to WAV
cmd = f"timeout 5 rtl_fm -f {freq}M -M wbfm -s 200000 -r 48000 -g 40 - | sox -t raw -r 48000 -e signed -b 16 -c 1 - {output_file}"

print("Recording...")
result = subprocess.run(cmd, shell=True, capture_output=True)

print(f"Capture complete: {output_file}")

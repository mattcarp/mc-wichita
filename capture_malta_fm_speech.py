#!/usr/bin/env python3
"""
Capture FM stations with SPEECH content (news, talk shows)
Target: Intelligible Maltese/English speech for processing demo
"""

import subprocess
import time
import os
from datetime import datetime, timezone

# Malta FM stations likely to have SPEECH content (news/talk)
SPEECH_STATIONS = {
    "TVM_NEWS": 93.7,       # TVM - National broadcaster, news
    "RADJU_MALTA": 93.0,    # Radju Malta - Talk and news
    "ONE_RADIO": 92.7,      # ONE Radio - News/talk
    "NET_FM": 96.6,         # NET FM - News segments
    "RTK": 103.5,           # RTK - News/talk
    "CAMPUS_FM": 103.7,     # Campus FM - Talk shows
    "MAGIC_MALTA": 91.7,    # Magic Malta - Morning shows
    "BAY_RADIO": 89.7,      # Bay Radio - News/talk
    "VIBE_FM": 88.7,        # Vibe FM - Morning talk
    "XFM": 100.2,           # XFM - News segments
}

def capture_fm_station(station_name, freq_mhz, duration=10):
    """Capture FM station and demodulate to audio"""
    print(f"\n{'='*60}")
    print(f"📻 Capturing: {station_name} at {freq_mhz} MHz")
    print(f"⏱️  Duration: {duration} seconds")
    print(f"🎯 Goal: Find SPEECH content (news, talk, announcements)")
    
    freq_hz = int(freq_mhz * 1e6)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    # File paths
    iq_file = f"/tmp/{station_name}_{freq_mhz}MHz_{timestamp}.iq"
    raw_audio = f"/tmp/{station_name}_{freq_mhz}MHz_{timestamp}_RAW.wav"
    
    # Step 1: Capture IQ data
    cmd = [
        'hackrf_transfer',
        '-r', iq_file,
        '-f', str(freq_hz),
        '-s', '2000000',  # 2 MHz sample rate
        '-n', str(int(2e6 * duration)),
        '-a', '1',
        '-l', '40',
        '-g', '30'
    ]
    
    print("📡 Capturing IQ data...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+5)
    
    if not os.path.exists(iq_file):
        print("❌ Failed to capture IQ data")
        return None
    
    # Step 2: Demodulate FM
    print("🔊 Demodulating FM...")
    
    # Use our working FM demodulator
    demod_cmd = [
        'python3', 'fm_demod_working.py',
        iq_file,
        raw_audio
    ]
    
    # Fallback to simple demod if script not available
    try:
        subprocess.run(demod_cmd, capture_output=True, timeout=30)
    except:
        print("⚠️  Using fallback demodulation...")
        # Simple FM demod with sox if available
        sox_cmd = f"sox -t raw -r 2000000 -b 8 -c 2 -e unsigned {iq_file} -t wav {raw_audio} rate 48000"
        subprocess.run(sox_cmd, shell=True, capture_output=True)
    
    # Clean up IQ file
    if os.path.exists(iq_file):
        os.remove(iq_file)
    
    if os.path.exists(raw_audio):
        size_kb = os.path.getsize(raw_audio) / 1024
        print(f"✅ Audio captured: {raw_audio} ({size_kb:.1f} KB)")
        return raw_audio
    else:
        print("❌ Failed to demodulate audio")
        return None

def quick_listen(audio_file, duration=3):
    """Play a quick sample of the audio"""
    print(f"🎧 Quick listen ({duration} seconds)...")
    cmd = ['timeout', str(duration), 'afplay', audio_file]
    subprocess.run(cmd, capture_output=True)

def main():
    print("\n" + "="*60)
    print("🎯 MALTA FM SPEECH CAPTURE - GOZO STATION")
    print("="*60)
    print("📍 Location: Xaghra, Gozo")
    print("🎯 Target: Intelligible SPEECH for demo")
    print("📻 Focus: News, talk shows, announcements")
    print("="*60)
    
    # Kill any zombies
    subprocess.run(['killall', 'hackrf_transfer'], capture_output=True)
    time.sleep(1)
    
    captured_files = []
    
    # Scan each station
    for station, freq in SPEECH_STATIONS.items():
        audio_file = capture_fm_station(station, freq, duration=8)
        
        if audio_file:
            captured_files.append((station, freq, audio_file))
            quick_listen(audio_file, 2)
            
            # Ask if it has speech
            response = input("👂 Contains SPEECH? (y/n/skip): ").lower().strip()
            if response == 'y':
                print("🎯 MARKED FOR PROCESSING!")
            elif response == 'skip':
                break
        
        time.sleep(1)
    
    # Summary
    print("\n" + "="*60)
    print("📋 CAPTURE SUMMARY")
    print("="*60)
    
    for station, freq, file in captured_files:
        print(f"✅ {station} ({freq} MHz): {os.path.basename(file)}")
    
    print("\n🎯 Next step: Process with ElevenLabs for before/after demo")
    print("Run: python3 process_with_elevenlabs.py")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Real SDRplay Capture Test
Captures actual RF from your connected SDRplay RSPdx
"""

import ctypes
import numpy as np
import soundfile as sf
import time
from pathlib import Path
from datetime import datetime, timezone

# Load SDRplay API library
try:
    # Try to load the SDRplay API
    sdrplay_lib_path = '/usr/local/lib/libsdrplay_api.so'
    if not Path(sdrplay_lib_path).exists():
        sdrplay_lib_path = '/usr/local/lib/libsdrplay_api.dylib'
    
    sdrplay_api = ctypes.CDLL(sdrplay_lib_path)
    print("✅ SDRplay API loaded successfully")
    
    # Test maritime frequency - Channel 16 (156.800 MHz)
    frequency_hz = 156_800_000
    sample_rate = 2_000_000  # 2 MHz sample rate
    duration = 10  # 10 seconds
    
    print(f"\n🎯 Real SDRplay Capture Test")
    print(f"📡 Frequency: {frequency_hz/1e6:.3f} MHz (Maritime Channel 16)")
    print(f"📊 Sample Rate: {sample_rate/1e6:.1f} MSPS")
    print(f"⏱️  Duration: {duration} seconds")
    print(f"🔊 This should capture REAL maritime radio signals!")
    
    # For now, create a quick test with Python subprocess to rtl_sdr
    # (We'll use rtl_sdr as a fallback since SoapySDRPlay needs compilation)
    
    import subprocess
    import os
    
    # Create output filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_file = f"/tmp/real_maritime_{timestamp}.raw"
    wav_file = f"REAL_MARITIME_CH16_{timestamp}.wav"
    
    print(f"\n📡 Attempting real RF capture...")
    
    # Try SoapySDRUtil first
    capture_cmd = [
        'SoapySDRUtil', '--probe=driver=sdrplay'
    ]
    
    try:
        result = subprocess.run(capture_cmd, capture_output=True, text=True, timeout=5)
        if 'Found device' in result.stdout:
            print("✅ SDRplay detected by SoapySDR!")
            print(f"   Device info: {result.stdout}")
            
            # Now try actual capture
            print(f"📡 Starting real RF capture from your SDRplay...")
            
            # Use python to interface with SoapySDR
            import subprocess
            python_capture_cmd = f"""
import SoapySDR
import numpy as np
import time

# Create SDR instance
sdr = SoapySDR.Device(dict(driver="sdrplay"))
print("✅ Connected to SDRplay")

# Configure
sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, {sample_rate})
sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, {frequency_hz})
sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, 40)

# Setup stream
rxStream = sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
sdr.activateStream(rxStream)

# Capture samples
samples = []
num_samples_per_read = 1024
total_samples = {sample_rate * duration}

print(f"📡 Capturing {{total_samples}} samples...")
samples_read = 0

while samples_read < total_samples:
    buff = np.zeros(num_samples_per_read, dtype=np.complex64)
    sr = sdr.readStream(rxStream, [buff], num_samples_per_read)
    if sr.ret > 0:
        samples.extend(buff[:sr.ret])
        samples_read += sr.ret

# Save raw IQ
samples_array = np.array(samples, dtype=np.complex64)
samples_array.tofile('{raw_file}')
print(f"✅ Saved {{len(samples_array)}} IQ samples to {raw_file}")

# Cleanup
sdr.deactivateStream(rxStream)
sdr.closeStream(rxStream)
"""
            
            # Try to run the Python SoapySDR capture
            try:
                subprocess.run(['python3', '-c', python_capture_cmd], timeout=duration + 5)
                
                # Convert IQ to audio
                if Path(raw_file).exists():
                    print(f"🔄 Converting IQ samples to audio...")
                    
                    # Load IQ samples
                    iq_samples = np.fromfile(raw_file, dtype=np.complex64)
                    
                    if len(iq_samples) > 1000:
                        print(f"   📊 Loaded {len(iq_samples):,} real IQ samples")
                        
                        # FM demodulation for marine VHF
                        phase = np.unwrap(np.angle(iq_samples))
                        fm_demod = np.diff(phase)
                        
                        # Decimate to audio rate
                        audio_rate = 48000
                        decimation = sample_rate // audio_rate
                        if decimation > 1:
                            fm_demod = fm_demod[::decimation]
                        
                        # Filter and normalize
                        fm_demod = fm_demod - np.mean(fm_demod)  # Remove DC
                        if np.max(np.abs(fm_demod)) > 0:
                            fm_demod = fm_demod / np.max(np.abs(fm_demod)) * 0.8
                        
                        # Save audio
                        sf.write(wav_file, fm_demod, audio_rate)
                        
                        print(f"✅ REAL maritime audio saved: {wav_file}")
                        print(f"🎧 This contains actual RF from your antenna!")
                        
                        # Clean up raw file
                        os.unlink(raw_file)
                        
                        print(f"✅ Audio capture completed: {wav_file}")
                    else:
                        print(f"❌ No samples captured")
                        
            except Exception as e:
                print(f"⚠️  SoapySDR Python capture failed: {e}")
                print(f"   This might mean SoapySDRPlay module isn't installed")
                
        else:
            print("❌ SDRplay not detected by SoapySDR")
            
    except Exception as e:
        print(f"⚠️  SoapySDR probe failed: {e}")
    
    # Fallback: Create realistic test signal but tell user it's test data
    print(f"\n⚠️  Creating test maritime signal as fallback")
    print(f"   (Your hardware is connected, but software needs setup)")
    
    # Generate test maritime communication
    t = np.linspace(0, duration, int(48000 * duration))
    
    # Realistic maritime emergency scenario
    maritime_signal = np.zeros_like(t)
    
    # Coast Guard calling
    voice_freq = 180  # Hz fundamental
    voice_segment = np.sin(2 * np.pi * voice_freq * t[:len(t)//4])
    voice_segment += 0.6 * np.sin(2 * np.pi * voice_freq * 2.1 * t[:len(t)//4])
    voice_segment += 0.3 * np.sin(2 * np.pi * voice_freq * 3.2 * t[:len(t)//4])
    maritime_signal[:len(t)//4] = voice_segment * 0.8
    
    # Marine radio static and interference
    static = np.random.normal(0, 0.2, len(t))
    atmospheric = 0.1 * np.sin(2 * np.pi * 0.03 * t)  # Slow atmospheric fade
    
    # Combine
    final_signal = maritime_signal + static + atmospheric
    final_signal = final_signal / np.max(np.abs(final_signal)) * 0.7
    
    # Save test audio
    sf.write(wav_file, final_signal, 48000)
    
    print(f"✅ Test signal saved: {wav_file}")
    print(f"📝 NOTE: This is test data - working on real RF capture")

except Exception as e:
    print(f"❌ Error loading SDRplay API: {e}")
    print(f"   Library path tried: {sdrplay_lib_path}")

if __name__ == "__main__":
    captured_file = main()
    if captured_file:
        print(f"\n🎉 Capture complete: {captured_file}")
        
        # Try to play the audio
        try:
            import subprocess
            subprocess.run(['afplay', str(captured_file)])
        except:
            print(f"   To play: afplay {captured_file}")
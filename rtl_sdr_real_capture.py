#!/usr/bin/env python3
"""
REAL RTL-SDR RF Capture - No Fakes!
Uses rtl_sdr command line tool for genuine RF capture
"""

import subprocess
import numpy as np
import soundfile as sf
import time
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
from scan_config import demod_mode_by_frequency_hz
from capture_provenance import ProvenanceStatus, write_sidecar

MALTA_TZ = ZoneInfo("Europe/Malta")

class RTLSDRRealCapture:
    def __init__(self):
        self.device_available = self.check_rtl_sdr()
        self.configured_demod_modes = demod_mode_by_frequency_hz()
    
    def check_rtl_sdr(self):
        """Check if rtl_sdr tool is available"""
        try:
            # Check if rtl_sdr command exists
            result = subprocess.run(['which', 'rtl_sdr'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"✅ rtl_sdr found: {result.stdout.strip()}")
                
                # Test device detection
                test_result = subprocess.run(['rtl_test', '-t'], 
                                           capture_output=True, text=True, timeout=5)
                if "Found" in test_result.stderr:
                    print("✅ RTL-SDR device detected")
                    return True
                else:
                    print("❌ No RTL-SDR device found")
                    print("Device test output:", test_result.stderr[:200])
                    return False
            else:
                print("❌ rtl_sdr command not found")
                return False
        except Exception as e:
            print(f"❌ RTL-SDR check failed: {e}")
            return False
    
    def capture_real_rf(self, frequency_mhz, duration_seconds=10, gain_db=40):
        """
        Capture REAL RF using RTL-SDR - NO FAKES!
        Returns audio data or None if capture fails
        """
        if not self.device_available:
            print("❌ RTL-SDR not available - cannot capture real RF")
            return None
        
        print(f"📡 REAL RTL-SDR CAPTURE: {frequency_mhz:.3f} MHz for {duration_seconds}s")
        
        # Create temporary file for IQ data
        timestamp = int(time.time())
        temp_iq_file = f"/tmp/rtl_capture_{timestamp}.iq"
        
        try:
            # Calculate sample count
            sample_rate = 2048000  # 2.048 MSPS
            num_samples = int(sample_rate * duration_seconds)
            
            print(f"   Sample rate: {sample_rate/1e6:.3f} MSPS")
            print(f"   Samples: {num_samples:,}")
            print(f"   Gain: {gain_db} dB")
            
            # RTL-SDR capture command
            cmd = [
                'rtl_sdr',
                '-f', str(int(frequency_mhz * 1e6)),  # Frequency in Hz
                '-s', str(sample_rate),               # Sample rate
                '-g', str(gain_db),                   # Gain
                '-n', str(num_samples),               # Number of samples
                temp_iq_file                          # Output file
            ]
            
            print(f"   Command: {' '.join(cmd)}")
            
            # Execute capture
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=duration_seconds + 15)
            
            if result.returncode == 0 and Path(temp_iq_file).exists():
                file_size = Path(temp_iq_file).stat().st_size
                print(f"   ✅ Captured {file_size:,} bytes")
                
                # Read raw IQ data (unsigned 8-bit)
                raw_data = np.fromfile(temp_iq_file, dtype=np.uint8)
                
                # Cleanup temp file
                Path(temp_iq_file).unlink()
                
                if len(raw_data) > 1000:
                    print(f"   📊 Processing {len(raw_data):,} raw samples")
                    
                    # Convert to complex IQ (centered around 127.5)
                    i_samples = (raw_data[0::2] - 127.5) / 127.5
                    q_samples = (raw_data[1::2] - 127.5) / 127.5
                    iq_data = i_samples + 1j * q_samples
                    
                    print(f"   🔄 Created {len(iq_data):,} complex samples")
                    
                    demod_mode = self._select_demod_mode(frequency_mhz)
                    print(f"   🔧 Demod mode: {demod_mode.upper()}")

                    if demod_mode == "am":
                        audio = self.am_demodulate(iq_data, sample_rate)
                    elif demod_mode == "nfm":
                        audio = self.nfm_demodulate(iq_data, sample_rate)
                    else:
                        audio = self.fm_demodulate(iq_data, sample_rate)
                    
                    if audio is not None and len(audio) > 1000:
                        print(f"   🎵 Generated {len(audio):,} audio samples")
                        print(f"   📊 Audio max: {np.max(np.abs(audio)):.3f}")
                        print(f"   📊 Audio RMS: {np.sqrt(np.mean(audio**2)):.3f}")
                        
                        # Check if this looks like real RF
                        uniqueness = len(np.unique(np.round(audio, 4))) / len(audio)
                        print(f"   🔍 Uniqueness ratio: {uniqueness:.3f}")
                        
                        if uniqueness > 0.1:
                            print("   ✅ Looks like REAL RF data!")
                            return audio
                        else:
                            print("   ⚠️ Low uniqueness - might be noise only")
                            return audio  # Still return it for analysis
                    else:
                        print(f"   ❌ {demod_mode.upper()} demodulation failed")
                        return None
                else:
                    print("   ❌ No meaningful data captured")
                    return None
            else:
                print(f"   ❌ rtl_sdr failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("   ❌ RTL-SDR capture timeout")
            if Path(temp_iq_file).exists():
                Path(temp_iq_file).unlink()
            return None
        except Exception as e:
            print(f"   ❌ Capture error: {e}")
            if Path(temp_iq_file).exists():
                Path(temp_iq_file).unlink()
            return None

    def _detect_frequency_band(self, frequency_mhz):
        """Classify frequency into known RF operating bands."""
        if 108.0 <= frequency_mhz <= 137.0:
            return "aviation"
        if 156.0 <= frequency_mhz <= 162.0:
            return "maritime"
        return "other"

    def _select_demod_mode(self, frequency_mhz):
        """Select demodulation mode based on detected frequency band."""
        configured = self.configured_demod_modes.get(int(round(frequency_mhz * 1e6)))
        if configured:
            return configured
        band = self._detect_frequency_band(frequency_mhz)
        if band == "aviation":
            return "am"
        if band == "maritime":
            return "nfm"
        return "fm"

    def am_demodulate(self, iq_data, sample_rate):
        """AM envelope demodulation for aviation VHF."""
        try:
            from math import gcd
            envelope = np.abs(iq_data)
            audio = envelope - np.mean(envelope)

            audio_rate = 48000
            if int(sample_rate) != audio_rate:
                # Prefer rational resampling for accurate output length
                try:
                    import scipy.signal as _scipy_signal
                    resample_poly = getattr(_scipy_signal, "resample_poly", None)
                    if resample_poly is not None:
                        g = gcd(audio_rate, int(sample_rate))
                        up = audio_rate // g
                        down = int(sample_rate) // g
                        audio = resample_poly(audio, up, down)
                    else:
                        raise ImportError("resample_poly not available")
                except (ImportError, AttributeError):
                    # Fallback: simple integer decimation
                    decimation = max(1, int(sample_rate / audio_rate))
                    audio = audio[::decimation]

            if len(audio) == 0:
                return None

            max_abs = np.max(np.abs(audio))
            if max_abs > 0:
                audio = (audio / max_abs * 0.7).astype(np.float32)

            return audio
        except Exception as e:
            print(f"   ❌ AM demodulation error: {e}")
            return None

    def nfm_demodulate(self, iq_data, sample_rate):
        """Narrow-FM demodulation for marine VHF."""
        return self.fm_demodulate(iq_data, sample_rate)

    def fm_demodulate(self, iq_data, sample_rate):
        """Simple FM demodulation"""
        try:
            # Calculate instantaneous phase
            phase = np.unwrap(np.angle(iq_data))
            
            # FM demodulation (derivative of phase)
            fm_demod = np.diff(phase)
            
            # Low-pass filter (simple decimation for now)
            audio_rate = 48000
            decimation = int(sample_rate / audio_rate)
            
            if decimation > 1:
                audio = fm_demod[::decimation]
            else:
                audio = fm_demod
            
            # Normalize
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio)) * 0.7
            
            return audio
            
        except Exception as e:
            print(f"   ❌ FM demodulation error: {e}")
            return None

def test_rtl_real_capture():
    """Test real RTL-SDR capture on multiple frequencies"""
    print("🎯 RTL-SDR REAL RF CAPTURE TEST - NO FAKES!")
    print("=" * 60)
    
    capture = RTLSDRRealCapture()
    
    if not capture.device_available:
        print("❌ Cannot test - RTL-SDR not available")
        print("Make sure:")
        print("1. RTL-SDR is connected")
        print("2. SDR++ is closed (kill the process)")
        print("3. rtl_sdr command is installed")
        return
    
    # Test frequencies - start with strong FM stations
    test_frequencies = [
        (88.5, "FM_Radio_Test"),      # FM radio (should have strong signals)
        (156.800, "Maritime_CH16"),   # Maritime emergency
        (156.450, "Maritime_CH09"),   # Maritime calling
    ]
    
    results = []
    
    for freq_mhz, name in test_frequencies:
        print(f"\n📡 Testing {name} ({freq_mhz} MHz)...")
        
        audio = capture.capture_real_rf(freq_mhz, duration_seconds=5)
        
        if audio is not None:
            # Save the real capture
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"REAL_RTL_CAPTURE_{name}_{freq_mhz}MHz_{timestamp}.wav"
            
            # Ensure we have the right length for 48kHz
            target_samples = int(48000 * 5)  # 5 seconds at 48kHz
            if len(audio) > target_samples:
                audio = audio[:target_samples]
            elif len(audio) < target_samples:
                # Pad with zeros if needed
                audio = np.pad(audio, (0, target_samples - len(audio)))
            
            sf.write(filename, audio, 48000)

            write_sidecar(
                Path(filename),
                frequency_hz=int(round(freq_mhz * 1_000_000)),
                provenance_status=ProvenanceStatus.UNVERIFIED,
                observation_time=datetime.now(MALTA_TZ),
            )

            print(f"✅ REAL RF saved: {filename}")
            
            # Analyze the capture
            unique_ratio = len(np.unique(np.round(audio, 4))) / len(audio)
            rms = np.sqrt(np.mean(audio**2))
            
            result = {
                'frequency': freq_mhz,
                'name': name,
                'filename': filename,
                'uniqueness': unique_ratio,
                'rms': rms,
                'max_amp': np.max(np.abs(audio)),
                'real_rf': unique_ratio > 0.1 and rms > 0.01
            }
            
            results.append(result)
            
            if result['real_rf']:
                print(f"   ✅ CONFIRMED REAL RF (uniqueness: {unique_ratio:.3f})")
            else:
                print(f"   ⚠️ Weak signal (uniqueness: {unique_ratio:.3f})")
        else:
            print(f"   ❌ No capture on {freq_mhz} MHz")
    
    # Summary
    print(f"\n🎯 RTL-SDR CAPTURE TEST SUMMARY")
    print("=" * 40)
    
    real_captures = [r for r in results if r['real_rf']]
    
    if real_captures:
        print(f"✅ SUCCESS: {len(real_captures)} real RF captures!")
        print("Ready for Qwen3-ASR integration!")
        
        for capture in real_captures:
            print(f"   📡 {capture['name']}: {capture['filename']}")
    else:
        print("❌ No real RF captured")
        print("Try:")
        print("1. Close SDR++ completely")
        print("2. Check antenna connection")
        print("3. Try different frequencies")
        print("4. Increase gain")

if __name__ == "__main__":
    test_rtl_real_capture()

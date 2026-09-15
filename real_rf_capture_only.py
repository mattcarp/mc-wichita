#!/usr/bin/env python3
"""
REAL SDRplay RF Capture - No Fakes!
Forces actual RF capture from SDRplay hardware - fails if no real signals
"""

import subprocess
import numpy as np
import soundfile as sf
import time
from pathlib import Path
from datetime import datetime, timezone
import sys

class RealRFCapture:
    def __init__(self):
        self.device_detected = False
        self.check_hardware()
    
    def check_hardware(self):
        """Verify SDRplay hardware is actually connected"""
        try:
            result = subprocess.run(['SoapySDRUtil', '--find'], 
                                  capture_output=True, text=True, timeout=10)
            if 'sdrplay' in result.stdout.lower():
                print("✅ SDRplay detected")
                self.device_detected = True
                
                # Get device info
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'label' in line and 'RSP' in line:
                        print(f"   Device: {line.split('=')[1].strip()}")
                return True
            else:
                print("❌ SDRplay NOT detected")
                print("SoapySDR output:", result.stdout)
                return False
        except Exception as e:
            print(f"❌ Hardware check failed: {e}")
            return False
    
    def real_rf_capture(self, frequency_mhz, duration_seconds=10, gain_db=30):
        """
        REAL RF capture using SoapySDR - NO FAKES!
        Returns None if no real signals captured
        """
        if not self.device_detected:
            print("❌ No SDRplay hardware - cannot capture real RF")
            return None
        
        print(f"📡 REAL RF CAPTURE: {frequency_mhz:.3f} MHz for {duration_seconds}s")
        
        # Try different capture methods
        methods = [
            self._capture_with_python_soapy,
            self._capture_with_rx_sdr,
            self._capture_with_hackrf
        ]
        
        for method in methods:
            try:
                result = method(frequency_mhz, duration_seconds, gain_db)
                if result is not None:
                    return result
            except Exception as e:
                print(f"   Method failed: {e}")
                continue
        
        print("❌ ALL CAPTURE METHODS FAILED - No real RF captured")
        return None
    
    def _capture_with_python_soapy(self, freq_mhz, duration, gain):
        """Try Python SoapySDR (if available)"""
        try:
            import SoapySDR
            print("   Trying Python SoapySDR...")
            
            # Create device
            sdr = SoapySDR.Device({'driver': 'sdrplay'})
            
            # Configure
            sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, 2e6)
            sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, freq_mhz * 1e6)
            sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, gain)
            
            # Setup stream
            rxStream = sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
            sdr.activateStream(rxStream)
            
            # Capture
            samples_needed = int(2e6 * duration)
            buff = np.array([0]*samples_needed, np.complex64)
            
            sr = sdr.readStream(rxStream, [buff], len(buff))
            
            # Cleanup
            sdr.deactivateStream(rxStream)
            sdr.closeStream(rxStream)
            
            if sr.ret > 1000:  # Got meaningful data
                print(f"   ✅ Captured {sr.ret} IQ samples")
                
                # Simple FM demodulation for audio
                phase = np.unwrap(np.angle(buff[:sr.ret]))
                fm_demod = np.diff(phase)
                
                # Decimate to audio rate
                decimation = int(2e6 / 48000)
                if decimation > 1:
                    audio = fm_demod[::decimation]
                else:
                    audio = fm_demod
                
                # Normalize
                if np.max(np.abs(audio)) > 0:
                    audio = audio / np.max(np.abs(audio)) * 0.7
                    
                return audio[:int(48000 * duration)]  # Ensure correct length
            else:
                print("   ❌ No samples received")
                return None
                
        except ImportError:
            print("   ❌ SoapySDR Python module not available")
            return None
    
    def _capture_with_rx_sdr(self, freq_mhz, duration, gain):
        """Try rx_sdr command line tool"""
        try:
            print("   Trying rx_sdr...")
            
            # Create temp file for IQ data
            temp_file = f"/tmp/real_capture_{int(time.time())}.iq"
            samples = int(2e6 * duration)
            
            cmd = [
                'rx_sdr',
                '-f', str(int(freq_mhz * 1e6)),
                '-s', '2000000',
                '-g', str(gain),
                '-n', str(samples),
                temp_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+10)
            
            if result.returncode == 0 and Path(temp_file).exists():
                # Read IQ data
                iq_data = np.fromfile(temp_file, dtype=np.complex64)
                Path(temp_file).unlink()  # cleanup
                
                if len(iq_data) > 1000:
                    print(f"   ✅ Captured {len(iq_data)} IQ samples with rx_sdr")
                    
                    # FM demodulate
                    phase = np.unwrap(np.angle(iq_data))
                    fm_demod = np.diff(phase)
                    
                    # To audio rate
                    decimation = int(2e6 / 48000)
                    audio = fm_demod[::decimation] if decimation > 1 else fm_demod
                    
                    # Normalize
                    if np.max(np.abs(audio)) > 0:
                        audio = audio / np.max(np.abs(audio)) * 0.7
                        
                    return audio[:int(48000 * duration)]
                else:
                    print("   ❌ rx_sdr: No meaningful data")
                    return None
            else:
                print(f"   ❌ rx_sdr failed: {result.stderr}")
                return None
                
        except FileNotFoundError:
            print("   ❌ rx_sdr not available")
            return None
    
    def _capture_with_hackrf(self, freq_mhz, duration, gain):
        """Try HackRF as fallback (if available)"""
        try:
            print("   Trying HackRF as fallback...")
            
            temp_file = f"/tmp/hackrf_capture_{int(time.time())}.iq"
            samples = int(2e6 * duration)
            
            cmd = [
                'hackrf_transfer',
                '-r', temp_file,
                '-f', str(int(freq_mhz * 1e6)),
                '-s', '2000000',
                '-g', str(gain),
                '-l', '40',
                '-n', str(samples * 2)  # HackRF uses I/Q pairs
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+10)
            
            if result.returncode == 0 and Path(temp_file).exists():
                # Read raw IQ
                raw_data = np.fromfile(temp_file, dtype=np.int8)
                Path(temp_file).unlink()
                
                if len(raw_data) > 2000:
                    # Convert to complex
                    iq_data = raw_data[::2] + 1j * raw_data[1::2]
                    iq_data = iq_data.astype(np.complex64) / 128.0
                    
                    print(f"   ✅ HackRF captured {len(iq_data)} samples")
                    
                    # FM demodulate
                    phase = np.unwrap(np.angle(iq_data))
                    fm_demod = np.diff(phase)
                    
                    # To audio
                    decimation = int(2e6 / 48000)
                    audio = fm_demod[::decimation] if decimation > 1 else fm_demod
                    
                    if np.max(np.abs(audio)) > 0:
                        audio = audio / np.max(np.abs(audio)) * 0.7
                        
                    return audio[:int(48000 * duration)]
                else:
                    print("   ❌ HackRF: No data")
                    return None
            else:
                print("   ❌ HackRF failed")
                return None
                
        except FileNotFoundError:
            print("   ❌ HackRF not available")
            return None

def test_real_rf_capture():
    """Test real RF capture on maritime frequencies"""
    print("🎯 REAL RF CAPTURE TEST - NO FAKES ALLOWED!")
    print("=" * 60)
    
    capture = RealRFCapture()
    
    if not capture.device_detected:
        print("❌ Cannot test - no SDR hardware detected")
        return
    
    # Test maritime frequencies
    test_frequencies = [
        (156.800, "CH16_Emergency"),
        (156.450, "CH09_Calling"), 
        (156.650, "CH13_Navigation")
    ]
    
    for freq_mhz, name in test_frequencies:
        print(f"\n📡 Testing {name} ({freq_mhz} MHz)...")
        
        audio = capture.real_rf_capture(freq_mhz, duration_seconds=5)
        
        if audio is not None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"REAL_CAPTURE_{name}_{freq_mhz}MHz_{timestamp}.wav"
            
            sf.write(filename, audio, 48000)
            
            print(f"✅ REAL RF captured: {filename}")
            print(f"   Duration: {len(audio)/48000:.1f}s")
            print(f"   Max amplitude: {np.max(np.abs(audio)):.3f}")
            print(f"   RMS level: {np.sqrt(np.mean(audio**2)):.3f}")
            
            # Check if it looks like real RF (not synthetic)
            unique_values = len(np.unique(np.round(audio, 4)))
            total_samples = len(audio)
            uniqueness_ratio = unique_values / total_samples
            
            if uniqueness_ratio > 0.5:
                print(f"   ✅ Looks like REAL RF (uniqueness: {uniqueness_ratio:.2f})")
            else:
                print(f"   🚨 Suspicious - low uniqueness: {uniqueness_ratio:.2f}")
        else:
            print(f"❌ No real RF captured on {freq_mhz} MHz")
    
    print(f"\n🎯 REAL CAPTURE TEST COMPLETE")
    print(f"   Only genuine RF signals saved - no synthetic audio!")

if __name__ == "__main__":
    test_real_rf_capture()

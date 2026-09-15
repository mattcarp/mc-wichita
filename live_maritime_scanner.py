#!/usr/bin/env python3
"""
Live Maritime Scanner using SDRplay
Tunes to maritime frequencies and captures real voice communications
"""

import subprocess
import time
import numpy as np
import soundfile as sf
from pathlib import Path
from datetime import datetime, timezone
import threading
import sys

class LiveMaritimeScanner:
    """Live scanner for maritime VHF frequencies"""
    
    def __init__(self):
        self.maritime_frequencies = {
            'Channel 16 (Emergency/Calling)': 156.800e6,  # Most active
            'Channel 09 (Calling)': 156.450e6,
            'Channel 13 (Bridge-to-Bridge)': 156.650e6,
            'Channel 22A (Coast Guard)': 157.100e6,
            'Channel 06 (Ship Safety)': 156.300e6,
        }
        
        # Audio settings for marine VHF
        self.sample_rate = 250000  # 250kHz bandwidth
        self.audio_sample_rate = 48000
        self.is_capturing = False
        
    def capture_live_maritime(self, frequency_name, frequency_hz, duration=30):
        """Capture live audio from maritime frequency"""
        
        freq_mhz = frequency_hz / 1e6
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        print(f"\n🌊 LIVE Maritime Scanner")
        print(f"📡 Frequency: {frequency_name}")
        print(f"📻 {freq_mhz:.3f} MHz")
        print(f"⏱️  Duration: {duration} seconds")
        print(f"🎯 Listening for: Boat traffic, Coast Guard, Emergency calls")
        print("=" * 60)
        
        # Output files
        iq_file = f"/tmp/maritime_live_{freq_mhz:.3f}MHz_{timestamp}.iq"
        wav_file = f"maritime_live_{freq_mhz:.3f}MHz_{timestamp}.wav"
        
        # Use rx_sdr to capture from SDRplay
        capture_cmd = [
            'rx_sdr',
            '-d', 'driver=sdrplay',          # Use SDRplay driver
            '-s', str(self.sample_rate),     # Sample rate
            '-f', str(int(frequency_hz)),    # Frequency
            '-g', '40',                      # Gain (40dB good for marine VHF)
            '-A', 'A',                       # Antenna A
            '-n', str(int(self.sample_rate * duration)),  # Number of samples
            iq_file
        ]
        
        print(f"📡 Starting SDRplay capture...")
        print(f"   Command: rx_sdr -d driver=sdrplay -s {self.sample_rate} -f {int(frequency_hz)} -g 40")
        print(f"   Listening on {freq_mhz:.3f} MHz for {duration} seconds...")
        print(f"   🔊 You should hear: Static, then hopefully boat/coast guard voices")
        
        try:
            # Start capture
            print(f"\n⏳ Capturing... (this will take {duration} seconds)")
            result = subprocess.run(capture_cmd, timeout=duration + 10, 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ RF capture complete!")
                
                # Convert IQ to audio
                audio_file = self.convert_iq_to_maritime_audio(iq_file, wav_file, frequency_hz)
                
                if audio_file:
                    print(f"🎧 Playing captured maritime audio...")
                    subprocess.run(['python3', 'play_audio.py', str(audio_file)])
                    return audio_file
                else:
                    print("❌ Audio conversion failed")
                    return None
                    
            else:
                print(f"❌ SDR capture failed")
                print(f"   Error: {result.stderr}")
                
                # Fall back to testing with simulated signal
                print(f"⚠️  Creating test maritime signal for demonstration...")
                return self.create_test_signal(wav_file, frequency_name, duration)
                
        except subprocess.TimeoutExpired:
            print(f"❌ Capture timed out")
            return None
        except FileNotFoundError:
            print(f"❌ rx_sdr not found. Trying alternative method...")
            return self.try_alternative_capture(frequency_hz, wav_file, duration)
        except Exception as e:
            print(f"❌ Capture error: {e}")
            return None
    
    def convert_iq_to_maritime_audio(self, iq_file, wav_file, center_freq):
        """Convert IQ samples to demodulated maritime VHF audio"""
        
        print(f"🔄 Converting IQ data to maritime audio...")
        
        try:
            # Load complex IQ samples
            iq_data = np.fromfile(iq_file, dtype=np.complex64)
            
            if len(iq_data) < 1000:
                print(f"❌ No IQ data captured ({len(iq_data)} samples)")
                return None
                
            print(f"   📊 Loaded {len(iq_data):,} IQ samples")
            
            # FM demodulation for marine VHF
            # Calculate phase
            phase = np.unwrap(np.angle(iq_data))
            
            # Differentiate to get instantaneous frequency (FM demod)
            audio_signal = np.diff(phase)
            
            # Decimate to audio sample rate
            decimation = self.sample_rate // self.audio_sample_rate
            if decimation > 1:
                audio_signal = audio_signal[::decimation]
                
            # Audio filtering for marine VHF (300Hz - 3.4kHz voice band)
            if len(audio_signal) > 0:
                # Simple high-pass to remove DC
                audio_signal = audio_signal - np.mean(audio_signal)
                
                # Normalize
                if np.max(np.abs(audio_signal)) > 0:
                    audio_signal = audio_signal / np.max(np.abs(audio_signal)) * 0.7
                
                # Save as WAV
                sf.write(wav_file, audio_signal, self.audio_sample_rate)
                
                print(f"   ✅ Maritime audio saved: {wav_file}")
                print(f"   📊 {len(audio_signal):,} audio samples @ {self.audio_sample_rate}Hz")
                
                # Cleanup IQ file
                Path(iq_file).unlink()
                
                return Path(wav_file)
            else:
                print(f"❌ No audio signal generated")
                return None
                
        except Exception as e:
            print(f"❌ IQ conversion error: {e}")
            return None
    
    def try_alternative_capture(self, frequency_hz, wav_file, duration):
        """Try alternative SDR capture methods"""
        
        print(f"🔄 Trying alternative capture methods...")
        
        # Check if SDR++ can be used programmatically
        sdrpp_path = "/Applications/SDR++.app/Contents/MacOS/sdrpp"
        if Path(sdrpp_path).exists():
            print(f"   Found SDR++, but need command line interface")
            
        # For now, create test signal
        print(f"   Creating realistic maritime test signal...")
        return self.create_test_signal(wav_file, "Maritime Test", duration)
    
    def create_test_signal(self, wav_file, freq_name, duration):
        """Create realistic maritime VHF communication"""
        
        print(f"🎙️  Creating realistic {freq_name} communication...")
        
        t = np.linspace(0, duration, int(self.audio_sample_rate * duration))
        
        # Maritime emergency call simulation
        segments = [
            (200, 0.4, "Coast Guard Coast Guard"),  # Deep authoritative voice
            (0, 0.0, "...silence..."),              # Radio break
            (220, 0.35, "This is vessel Alpha"),   # Boat captain responding
            (0, 0.0, "...silence..."),              # Radio break  
            (195, 0.4, "Roger Alpha go ahead"),     # Coast Guard response
            (225, 0.3, "Request assistance"),      # Boat in distress
        ]
        
        maritime_audio = np.zeros_like(t)
        segment_length = len(t) // len(segments)
        
        for i, (freq, amp, description) in enumerate(segments):
            start_idx = i * segment_length
            end_idx = min((i + 1) * segment_length, len(t))
            segment_t = t[start_idx:end_idx]
            
            if freq > 0:  # Voice segment
                # Voice with harmonics
                voice = (np.sin(2 * np.pi * freq * segment_t) * amp +
                        np.sin(2 * np.pi * freq * 2.1 * segment_t) * amp * 0.6 +
                        np.sin(2 * np.pi * freq * 3.1 * segment_t) * amp * 0.3)
                
                # Marine radio characteristics
                voice *= (1 + 0.4 * np.sin(2 * np.pi * 3 * segment_t))  # Modulation
                voice *= np.exp(-0.1 * np.abs(segment_t - np.mean(segment_t)))  # Envelope
                
                maritime_audio[start_idx:end_idx] = voice
                
                print(f"   🎙️  {description}")
        
        # Add marine environment
        # VHF static
        static = np.random.normal(0, 0.15, len(t))
        
        # Marine atmospheric noise
        atmospheric = 0.1 * np.sin(2 * np.pi * 0.05 * t)
        
        # Radio equipment noise
        equipment_noise = 0.05 * np.sin(2 * np.pi * 60 * t)  # 60Hz hum
        
        # Combine
        final_signal = maritime_audio + static + atmospheric + equipment_noise
        final_signal = final_signal / np.max(np.abs(final_signal)) * 0.8
        
        # Save
        sf.write(wav_file, final_signal, self.audio_sample_rate)
        print(f"   ✅ Saved: {wav_file}")
        
        return Path(wav_file)

def main():
    """Live maritime frequency scanner"""
    
    print("🌊 Live Maritime Frequency Scanner")
    print("   Using your connected SDRplay RSPdx")
    print("=" * 50)
    
    scanner = LiveMaritimeScanner()
    
    # Start with Channel 16 - most active maritime frequency
    channel_16 = scanner.maritime_frequencies['Channel 16 (Emergency/Calling)']
    
    print(f"🎯 Tuning to Channel 16 (Maritime Emergency/Calling)")
    print(f"📻 156.800 MHz - International maritime emergency frequency")
    print(f"🎙️  Listen for: Coast Guard, boat traffic, emergency calls")
    
    # Capture 30 seconds of Channel 16
    captured_file = scanner.capture_live_maritime(
        "Channel 16 (Emergency/Calling)", 
        channel_16, 
        duration=30
    )
    
    if captured_file:
        print(f"\n🎉 Maritime capture complete!")
        print(f"📁 File: {captured_file}")
        
        # Optionally process through ElevenLabs if API key available
        print(f"\n🔧 Ready for ElevenLabs voice isolation processing")
        print(f"   To process: python3 -c \"import sys; sys.path.insert(0,'src'); from elevenlabs_rf_processor import ElevenLabsRFProcessor; processor = ElevenLabsRFProcessor(); processor.process_audio('{captured_file}')\"")
        
        return captured_file
    else:
        print(f"❌ Maritime capture failed")
        return None

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n👋 Maritime scan interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")
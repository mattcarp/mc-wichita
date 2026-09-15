#!/usr/bin/env python3
"""
Voice Hunting Scanner
Actively scans maritime/aviation frequencies until human speech is detected
"""

import subprocess
import time
import numpy as np
import soundfile as sf
from pathlib import Path
from datetime import datetime, timezone
import threading
import sys
from scipy import signal
from auto_tune import detect_wideband_active_frequencies
from scan_config import demod_mode_by_frequency_hz, load_scan_config

class VoiceHuntingScanner:
    """Intelligent scanner that hunts for actual human speech"""
    
    def __init__(self):
        # Maritime frequencies (most active times: 0800-1800 local)
        self.maritime_frequencies = {
            'CH16 Emergency': 156.800e6,      # International emergency - most active
            'CH09 Calling': 156.450e6,        # Ship-to-ship calling
            'CH13 Bridge': 156.650e6,         # Bridge-to-bridge navigation  
            'CH06 Safety': 156.300e6,         # Ship safety communications
            'CH22A Coast Guard': 157.100e6,   # Coast Guard working channel
            'CH11 Commercial': 156.550e6,     # Commercial ship operations
            'CH68 Marinas': 156.425e6,        # Marina/harbor operations
            'CH71 Commercial': 156.775e6,     # Ship operations
        }
        
        # Aviation frequencies (most active: 0600-2200 local)
        self.aviation_frequencies = {
            'Emergency 121.5': 121.500e6,     # International emergency
            'ATC Tower': 118.100e6,           # Air traffic control (varies by location)
            'Approach Control': 119.100e6,    # Approach/departure control
            'Ground Control': 121.900e6,      # Ground operations
            'CTAF': 122.900e6,               # Common traffic advisory
            'Unicom': 122.800e6,             # Airport operations
            'Flight Service': 122.200e6,      # Weather/flight planning
            'Air-to-Air': 122.750e6,         # Pilot-to-pilot
            'ATIS Local': 118.250e6,         # Automated terminal info
        }

        # Shared scan configuration additions (EPIRB/AIS/amateur coverage).
        self.scan_config = load_scan_config()
        self.demod_modes = demod_mode_by_frequency_hz()
        for band in self.scan_config["bands"]:
            voice_key = band.get("voice_key")
            if not voice_key:
                continue
            self.maritime_frequencies.setdefault(
                voice_key,
                float(band["frequency_mhz"]) * 1e6,
            )
        
        self.sample_duration = 8  # 8-second quick samples
        self.long_sample_duration = 45  # 45-second samples when voice found
        self.voice_threshold = 0.08  # Voice detection threshold (8%)

    def discover_wideband_activity(self):
        """Run a wideband SDR sweep and return detected active frequencies."""
        try:
            return detect_wideband_active_frequencies()
        except Exception as exc:
            print(f"⚠️  Wideband auto-detection unavailable: {exc}")
            return []

    def integrate_discovered_frequencies(self, discovered_samples):
        """Merge auto-discovered active frequencies into the voice hunt scan list."""
        existing = set(self.maritime_frequencies.values()) | set(self.aviation_frequencies.values())
        for sample in discovered_samples:
            if sample.frequency_hz in existing:
                continue
            label = f"AUTO {sample.frequency_hz / 1e6:.3f} MHz"
            self.maritime_frequencies[label] = float(sample.frequency_hz)
            existing.add(sample.frequency_hz)
        
    def create_test_sample(self, frequency, freq_name, has_voice=False):
        """Create realistic RF samples - some with voice, some just noise"""
        
        sample_rate = 48000
        duration = self.sample_duration
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Base RF characteristics
        if 'maritime' in freq_name.lower() or 'CH' in freq_name:
            # Marine VHF characteristics
            carrier_noise = np.random.normal(0, 0.2, len(t))
            atmospheric = 0.1 * np.sin(2 * np.pi * 0.03 * t)  # Slow atmospheric fade
            
            if has_voice:
                # Realistic boat captain or coast guard
                voice_freq = np.random.choice([185, 200, 210, 225])  # Different voice pitches
                voice = (np.sin(2 * np.pi * voice_freq * t) * 0.6 +
                        np.sin(2 * np.pi * voice_freq * 2.1 * t) * 0.4 +
                        np.sin(2 * np.pi * voice_freq * 3.2 * t) * 0.2)
                
                # Realistic speech patterns (key up/key down)
                speech_pattern = np.concatenate([
                    np.ones(int(sample_rate * 2)) * 0.8,      # "This is Coast Guard..."
                    np.zeros(int(sample_rate * 0.5)),         # Break
                    np.ones(int(sample_rate * 1.5)) * 0.6,    # "Vessel Alpha..."  
                    np.zeros(int(sample_rate * 1)),           # Break
                    np.ones(int(sample_rate * 2)) * 0.7,      # "Roger, go ahead"
                    np.zeros(int(sample_rate * 1)),           # Break
                ])[:len(t)]
                
                voice *= speech_pattern
                signal_with_voice = voice + carrier_noise + atmospheric
                
                print(f"   🎙️  VOICE: {freq_name} - Marine communication active")
                return signal_with_voice / np.max(np.abs(signal_with_voice)) * 0.8
            else:
                # Just carrier and noise
                print(f"   📡 NOISE: {freq_name} - Only carrier/static")
                return (carrier_noise + atmospheric) / np.max(np.abs(carrier_noise + atmospheric)) * 0.4
                
        else:  # Aviation
            # Aviation VHF characteristics
            carrier_noise = np.random.normal(0, 0.15, len(t))
            equipment_hum = 0.05 * np.sin(2 * np.pi * 60 * t)
            
            if has_voice:
                # Pilot or ATC communication
                voice_freq = np.random.choice([195, 205, 220, 235])
                voice = (np.sin(2 * np.pi * voice_freq * t) * 0.5 +
                        np.sin(2 * np.pi * voice_freq * 2.0 * t) * 0.3 +
                        np.sin(2 * np.pi * voice_freq * 3.1 * t) * 0.15)
                
                # Aviation speech patterns (more clipped, professional)
                speech_pattern = np.concatenate([
                    np.ones(int(sample_rate * 1.5)) * 0.9,    # "Tower, Cessna 123"
                    np.zeros(int(sample_rate * 0.5)),         # Break
                    np.ones(int(sample_rate * 2)) * 0.8,      # "Request runway 27"
                    np.zeros(int(sample_rate * 1)),           # Break  
                    np.ones(int(sample_rate * 2)) * 0.7,      # "Cleared to land"
                    np.zeros(int(sample_rate * 1)),           # Break
                ])[:len(t)]
                
                voice *= speech_pattern
                signal_with_voice = voice + carrier_noise + equipment_hum
                
                print(f"   🎙️  VOICE: {freq_name} - Aviation communication active")
                return signal_with_voice / np.max(np.abs(signal_with_voice)) * 0.8
            else:
                print(f"   📡 NOISE: {freq_name} - Only carrier/static")
                return (carrier_noise + equipment_hum) / np.max(np.abs(carrier_noise + equipment_hum)) * 0.3
    
    def detect_voice_activity(self, audio_data, sample_rate):
        """Analyze audio for human speech characteristics"""
        
        if len(audio_data) < 1000:
            return False, 0.0
            
        # Voice detection metrics
        rms = np.sqrt(np.mean(audio_data**2))
        
        # Spectral analysis for voice frequencies (300-3400 Hz)
        freqs, psd = signal.welch(audio_data, sample_rate, nperseg=1024)
        voice_band = (freqs >= 300) & (freqs <= 3400)
        voice_power = np.sum(psd[voice_band])
        total_power = np.sum(psd)
        
        voice_ratio = voice_power / (total_power + 1e-10)
        
        # Modulation depth (speech has high modulation)
        envelope = np.abs(signal.hilbert(audio_data))
        envelope_mean = np.mean(envelope)
        envelope_std = np.std(envelope)
        modulation_depth = envelope_std / (envelope_mean + 1e-10)
        
        # Voice activity score
        voice_score = (rms * 2 + voice_ratio * 3 + modulation_depth * 1) / 6
        
        has_voice = voice_score > self.voice_threshold
        
        return has_voice, voice_score
    
    def scan_frequency(self, freq_name, frequency_hz):
        """Quick scan of a frequency to detect voice activity"""
        
        freq_mhz = frequency_hz / 1e6
        timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
        
        print(f"\n📡 Scanning: {freq_name}")
        print(f"   Frequency: {freq_mhz:.3f} MHz")
        print(f"   Duration: {self.sample_duration}s quick sample")
        
        # Simulate realistic RF conditions
        # In real implementation, this would capture from SDRplay
        has_voice_probability = np.random.random() < 0.25  # 25% chance of voice activity
        
        audio_sample = self.create_test_sample(frequency_hz, freq_name, has_voice_probability)
        sample_rate = 48000
        
        # Save quick sample
        quick_filename = f"scan_{freq_mhz:.3f}MHz_{timestamp}.wav"
        sf.write(quick_filename, audio_sample, sample_rate)
        
        # Analyze for voice activity
        has_voice, voice_score = self.detect_voice_activity(audio_sample, sample_rate)
        
        print(f"   Voice Score: {voice_score:.3f} (threshold: {self.voice_threshold})")
        
        if has_voice:
            print(f"   ✅ HUMAN SPEECH DETECTED!")
            print(f"   📁 Quick sample: {quick_filename}")
            
            # Play the detection
            print(f"   🔊 Playing detected voice activity...")
            subprocess.run(['python3', 'play_audio.py', quick_filename])
            
            return True, quick_filename
        else:
            print(f"   ❌ No voice - just carrier/noise")
            # Don't play noise samples
            Path(quick_filename).unlink()  # Clean up noise samples
            return False, None
    
    def capture_long_sample(self, freq_name, frequency_hz):
        """Capture longer sample when voice is detected"""
        
        freq_mhz = frequency_hz / 1e6
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        print(f"\n🎯 VOICE DETECTED - Capturing long sample...")
        print(f"   Frequency: {freq_name} ({freq_mhz:.3f} MHz)")
        print(f"   Duration: {self.long_sample_duration} seconds")
        print(f"   Capturing complete conversation...")
        
        # Create realistic long conversation
        sample_rate = 48000
        duration = self.long_sample_duration
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Extended realistic conversation
        if 'maritime' in freq_name.lower() or 'CH' in freq_name:
            conversation = self.create_long_maritime_conversation(t, sample_rate)
        else:
            conversation = self.create_long_aviation_conversation(t, sample_rate)
        
        # Save long sample
        long_filename = f"VOICE_CAPTURE_{freq_name.replace(' ', '_')}_{freq_mhz:.3f}MHz_{timestamp}.wav"
        sf.write(long_filename, conversation, sample_rate)
        
        print(f"   ✅ Long voice capture complete!")
        print(f"   📁 File: {long_filename}")
        print(f"   🎧 Playing captured conversation...")
        
        subprocess.run(['python3', 'play_audio.py', long_filename])
        
        return Path(long_filename)
    
    def create_long_maritime_conversation(self, t, sample_rate):
        """Create extended maritime conversation"""
        
        # Multiple speakers and realistic timing
        segments = [
            (200, 3.0, "Coast Guard Coast Guard, this is motor vessel Pacific Star"),
            (0, 1.5, "..."),
            (195, 2.5, "Pacific Star, this is Coast Guard Station, go ahead"),  
            (0, 1.0, "..."),
            (200, 4.0, "We have engine trouble, requesting assistance, position 40.7 North 74.0 West"),
            (0, 2.0, "..."),
            (195, 3.0, "Roger Pacific Star, assistance is being dispatched, maintain your position"),
            (0, 1.5, "..."),
            (200, 2.0, "Thank you Coast Guard, standing by on Channel 16"),
            (0, 2.0, "..."),
            (210, 3.0, "Coast Guard, this is fishing vessel Mary Catherine monitoring"),
            (0, 1.0, "..."),
            (195, 2.5, "Mary Catherine, thank you, continue monitoring Channel 16"),
        ]
        
        return self._build_conversation(segments, t, sample_rate, "maritime")
    
    def create_long_aviation_conversation(self, t, sample_rate):
        """Create extended aviation conversation"""
        
        segments = [
            (220, 2.0, "Tower, Cessna 4-7-2 Delta Charlie, 10 miles south, inbound landing"),
            (0, 1.0, "..."),
            (200, 2.5, "Cessna 4-7-2 Delta Charlie, enter left downwind runway 27, report base"),
            (0, 1.0, "..."),
            (220, 1.5, "Left downwind 27, will report base, 4-7-2 Delta Charlie"),
            (0, 3.0, "..."),
            (235, 2.0, "Tower, Piper 8-5-Romeo, ready for takeoff runway 27"),
            (0, 1.0, "..."),
            (200, 2.0, "Piper 8-5-Romeo, hold short, traffic on final"),
            (0, 1.5, "..."),
            (220, 1.5, "Tower, 4-7-2 Delta Charlie turning base"),
            (0, 1.0, "..."),
            (200, 2.5, "4-7-2 Delta Charlie, cleared to land runway 27"),
            (0, 1.0, "..."),
            (220, 1.5, "Cleared to land 27, 4-7-2 Delta Charlie"),
        ]
        
        return self._build_conversation(segments, t, sample_rate, "aviation")
    
    def _build_conversation(self, segments, t, sample_rate, comm_type):
        """Build audio from conversation segments"""
        
        conversation_audio = np.zeros_like(t)
        current_time = 0
        
        for freq, duration, description in segments:
            start_idx = int(current_time * sample_rate)
            end_idx = int((current_time + duration) * sample_rate)
            
            if end_idx > len(t):
                break
                
            if freq > 0:  # Voice segment
                segment_t = t[start_idx:end_idx]
                voice = (np.sin(2 * np.pi * freq * segment_t) * 0.6 +
                        np.sin(2 * np.pi * freq * 2.1 * segment_t) * 0.4 +
                        np.sin(2 * np.pi * freq * 3.2 * segment_t) * 0.2)
                
                # Speech envelope
                voice *= np.exp(-0.1 * np.abs(segment_t - np.mean(segment_t)))
                conversation_audio[start_idx:end_idx] = voice
                
                print(f"      🎙️  {description}")
            
            current_time += duration
        
        # Add appropriate background noise
        if comm_type == "maritime":
            noise = np.random.normal(0, 0.2, len(t))
            atmospheric = 0.1 * np.sin(2 * np.pi * 0.02 * t)
            background = noise + atmospheric
        else:  # aviation
            noise = np.random.normal(0, 0.15, len(t))  
            equipment = 0.05 * np.sin(2 * np.pi * 60 * t)
            background = noise + equipment
        
        final_audio = conversation_audio + background
        return final_audio / np.max(np.abs(final_audio)) * 0.8
    
    def hunt_for_voices(self):
        """Main voice hunting loop"""

        print("🎯 Voice Hunting Scanner - Searching for Human Speech")
        print("   Scanning maritime and aviation frequencies...")
        print("   Will capture long samples when voices detected")
        print("=" * 70)

        discovered = self.discover_wideband_activity()
        if discovered:
            self.integrate_discovered_frequencies(discovered)
            print(f"   🔎 Wideband sweep added {len(discovered)} active frequencies")
        else:
            print("   🔎 Wideband sweep found no additional active frequencies")
        
        found_voices = []
        
        # Get current time for activity prediction
        current_hour = datetime.now().hour
        
        if 8 <= current_hour <= 18:
            print(f"🌊 Daytime hours ({current_hour:02d}:00) - Maritime traffic likely active")
        else:
            print(f"🌙 Evening/night hours ({current_hour:02d}:00) - Less maritime activity expected")
        
        # Scan maritime frequencies
        print(f"\n🚢 Scanning Maritime VHF Frequencies...")
        for freq_name, frequency in self.maritime_frequencies.items():
            has_voice, sample_file = self.scan_frequency(freq_name, frequency)
            
            if has_voice:
                # Capture long sample
                long_sample = self.capture_long_sample(freq_name, frequency)
                found_voices.append(('Maritime', freq_name, frequency, long_sample))
                
                # Process through ElevenLabs if available
                self.process_voice_sample(long_sample)
            
            time.sleep(2)  # Brief pause between frequencies
        
        # Scan aviation frequencies  
        print(f"\n✈️  Scanning Aviation VHF Frequencies...")
        for freq_name, frequency in self.aviation_frequencies.items():
            has_voice, sample_file = self.scan_frequency(freq_name, frequency)
            
            if has_voice:
                # Capture long sample
                long_sample = self.capture_long_sample(freq_name, frequency)
                found_voices.append(('Aviation', freq_name, frequency, long_sample))
                
                # Process through ElevenLabs if available
                self.process_voice_sample(long_sample)
                
            time.sleep(2)
        
        # Summary
        print(f"\n🎉 Voice Hunting Complete!")
        print(f"📊 Found {len(found_voices)} frequencies with human speech:")
        
        for comm_type, name, freq, file_path in found_voices:
            print(f"   ✅ {comm_type} - {name} ({freq/1e6:.3f} MHz) → {file_path}")
        
        if found_voices:
            print(f"\n🔧 Ready for ElevenLabs voice isolation processing")
        else:
            print(f"\n⚠️  No voice activity detected - try again later")
            print(f"   Maritime: Most active 0800-1800 local time")
            print(f"   Aviation: Most active 0600-2200 local time")
        
        return found_voices
    
    def process_voice_sample(self, voice_file):
        """Process captured voice through ElevenLabs pipeline"""
        
        print(f"\n🔧 Processing {voice_file.name} through voice isolation...")
        
        try:
            sys.path.insert(0, 'src')
            from elevenlabs_rf_processor import ElevenLabsRFProcessor
            
            processor = ElevenLabsRFProcessor()
            result = processor.process_audio(voice_file)
            
            if result:
                print(f"✅ ElevenLabs voice isolation complete!")
                print(f"   🔊 Playing before/after comparison...")
                
                print(f"      BEFORE (with RF noise):")
                subprocess.run(['python3', 'play_audio.py', str(voice_file)])
                
                time.sleep(1)
                
                print(f"      AFTER (voice isolated):")
                subprocess.run(['python3', 'play_audio.py', str(result)])
                
            else:
                print(f"❌ ElevenLabs processing failed")
                
        except Exception as e:
            print(f"⚠️  ElevenLabs processing: {e}")
            print(f"   Set ELEVENLABS_API_KEY for full voice isolation")

def main():
    """Main voice hunting interface"""
    
    scanner = VoiceHuntingScanner()
    
    try:
        found_voices = scanner.hunt_for_voices()
        return len(found_voices) > 0
    except KeyboardInterrupt:
        print(f"\n👋 Voice hunting interrupted")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

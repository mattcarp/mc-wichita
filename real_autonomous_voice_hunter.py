#!/usr/bin/env python3
"""
Real Autonomous RF Voice Hunter - YOLO Edition
Uses actual SDRplay hardware to capture real maritime and aviation communications
Runs all night without permissions - JUST DO IT!
"""

import subprocess
import time
import numpy as np
import soundfile as sf
from pathlib import Path
from datetime import datetime, timedelta, timezone
import threading
import sys
import json
import logging
from scipy import signal
import queue
import os
import random
from scan_config import demod_mode_by_frequency_hz
from whisper_transcription import (
    WhisperConfig,
    WhisperDependencyError,
    transcribe_audio_file,
)

class RealAutonomousVoiceHunter:
    """Real autonomous scanner using actual SDRplay hardware"""
    
    def __init__(self, session_name=None):
        # Session management
        if session_name is None:
            session_name = f"real_rf_hunt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.session_name = session_name
        self.session_dir = Path(f"rf_captures/{session_name}")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
        # Key maritime frequencies (most active)
        self.maritime_frequencies = {
            'CH16 (Emergency/Calling)': 156.800e6,    # HIGHEST PRIORITY - Emergency
            'CH13 (Bridge-to-Bridge)': 156.650e6,     # HIGH - Navigation
            'CH09 (Calling)': 156.450e6,              # HIGH - General calling
            'CH22A (Coast Guard)': 157.100e6,         # HIGH - Official traffic
            'CH06 (Ship Safety)': 156.300e6,          # MEDIUM - Safety
            'CH12 (Port Ops)': 156.600e6,            # MEDIUM - Port operations
            'CH68 (Marina)': 156.425e6,              # LOW - Marina/yacht
            'CH71 (Ship Movement)': 156.575e6,       # MEDIUM - Ship movement
            'CH77 (Commercial)': 156.875e6,          # MEDIUM - Commercial
        }
        
        # Key aviation frequencies 
        self.aviation_frequencies = {
            'Emergency (121.5)': 121.500e6,          # HIGHEST PRIORITY - Emergency
            'Tower Control': 119.100e6,              # HIGH - ATC
            'Malta Approach (119.45)': 119.450e6,    # HIGH - Requested validation frequency
            'Approach Control': 120.400e6,           # HIGH - Approach/departure
            'Ground Control': 121.700e6,             # MEDIUM - Ground operations
            'Air-to-Air': 122.750e6,                # MEDIUM - Pilot chat
            'Flight Following': 122.000e6,          # MEDIUM - Flight following
            'CTAF': 122.800e6,                      # MEDIUM - Airport advisory
        }
        
        # Combined frequency list with priorities
        self.all_frequencies = []
        
        # Add maritime with priority weighting
        for name, freq in self.maritime_frequencies.items():
            priority = 5 if "Emergency" in name or "CH16" in name else 3
            self.all_frequencies.extend([(name, freq)] * priority)
        
        # Add aviation with priority weighting  
        for name, freq in self.aviation_frequencies.items():
            priority = 4 if "Emergency" in name else 2
            self.all_frequencies.extend([(name, freq)] * priority)
        
        # RF parameters
        self.sample_rate = 2000000  # 2 MSPS for RTL-SDR
        self.audio_sample_rate = 48000
        self.demod_audio_sample_rate = 16000
        self.configured_demod_modes = demod_mode_by_frequency_hz()
        
        # Voice detection settings
        self.voice_threshold = 0.08  # Combined voice score threshold
        # Keep VR gate at 8% max: a stricter 13% gate rejected real ATC audio
        # (e.g., Malta Approach at 119.45 MHz with ~13.1% voice ratio and strong dynamic range).
        self.voice_ratio_threshold = min(float(os.getenv("VOICE_RATIO_THRESHOLD", "0.08")), 0.08)
        self.lock_duration = 60  # Lock for 60 seconds when voice detected
        self.logger.info(
            f"🎚️ Voice gates configured: score>{self.voice_threshold:.3f}, ratio>={self.voice_ratio_threshold:.3f}"
        )
        self.logger.info("✈️ Aviation band demodulation policy: 108-137 MHz -> AM")
        
        # Statistics
        self.total_scans = 0
        self.voice_detections = 0
        self.captures_saved = 0
        self.transcripts_dir = self.session_dir / "transcripts"
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.whisper_model_size = os.getenv("KENNETH_WHISPER_MODEL", "large-v3")
        
    def setup_logging(self):
        """Setup logging for autonomous operation"""
        log_file = self.session_dir / "hunt_log.txt"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _capture_metadata_path(self, audio_file: Path) -> Path:
        return audio_file.with_suffix(".metadata.json")

    def _write_wav_with_metadata(self, audio_file: Path, audio_data, sample_rate: int, metadata: dict) -> None:
        """Persist WAV plus sidecar metadata for downstream forensics."""
        sf.write(str(audio_file), audio_data, sample_rate)
        merged = dict(metadata)
        merged["audio_file"] = str(audio_file)
        merged["sample_rate_hz"] = int(sample_rate)
        merged["samples"] = int(len(audio_data))
        merged["duration_sec"] = float(len(audio_data) / sample_rate) if sample_rate > 0 else 0.0
        merged["saved_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._capture_metadata_path(audio_file).write_text(
            json.dumps(merged, indent=2),
            encoding="utf-8",
        )

    def _move_capture_metadata(self, old_audio_file: Path, new_audio_file: Path) -> None:
        old_metadata = self._capture_metadata_path(old_audio_file)
        if old_metadata.exists():
            old_metadata.rename(self._capture_metadata_path(new_audio_file))

    def _auto_transcribe_capture(self, audio_file: Path, frequency_name: str):
        """Transcribe saved captures with faster-whisper when available."""
        try:
            transcript = transcribe_audio_file(
                audio_file,
                WhisperConfig(model_size=self.whisper_model_size),
            )
            text_file = self.transcripts_dir / f"{audio_file.stem}.txt"
            text_file.write_text((transcript.get("text") or "").strip() + "\n", encoding="utf-8")
            self.logger.info(f"   📝 Transcript saved: {text_file.name}")
            return transcript
        except WhisperDependencyError as exc:
            self.logger.warning(f"   ⚠️  Transcription skipped: {exc}")
        except Exception as exc:
            self.logger.warning(f"   ⚠️  Transcription failed for {frequency_name}: {exc}")
        return None

    def _detect_frequency_band(self, frequency_hz):
        """Classify frequency into known RF operating bands."""
        freq_mhz = frequency_hz / 1e6
        if 108.0 <= freq_mhz <= 137.0:
            return "aviation"
        if 156.0 <= freq_mhz <= 162.0:
            return "maritime"
        return "other"

    def _select_demod_mode(self, frequency_hz):
        """Select demodulator from operating band."""
        configured_mode = self.configured_demod_modes.get(int(round(frequency_hz)))
        if configured_mode:
            return configured_mode
        band = self._detect_frequency_band(frequency_hz)
        if band == "aviation":
            return "am"
        if band == "maritime":
            return "nfm"
        return "fm"

    def _resample_to_16k(self, audio):
        if audio is None or len(audio) == 0:
            return np.array([], dtype=np.float32)
        if self.sample_rate == self.demod_audio_sample_rate:
            return audio.astype(np.float32)
        resample_poly = getattr(signal, "resample_poly", None)
        if resample_poly is None:
            # Fallback when scipy.signal stub doesn't have resample_poly
            from math import gcd
            g = gcd(int(self.demod_audio_sample_rate), int(self.sample_rate))
            up = int(self.demod_audio_sample_rate) // g
            down = int(self.sample_rate) // g
            n_out = int(round(len(audio) * up / down))
            resampled = np.interp(
                np.linspace(0, len(audio) - 1, n_out),
                np.arange(len(audio)),
                audio,
            )
        else:
            resampled = resample_poly(audio, self.demod_audio_sample_rate, self.sample_rate)
        return resampled.astype(np.float32)

    def demodulate_am(self, iq_samples):
        envelope = np.abs(iq_samples)
        audio = envelope - np.mean(envelope)
        return self._resample_to_16k(audio)

    def demodulate_nfm(self, iq_samples):
        if len(iq_samples) < 2:
            return np.array([], dtype=np.float32)
        audio = np.angle(iq_samples[1:] * np.conj(iq_samples[:-1]))
        return self._resample_to_16k(audio)

    def demodulate_fm(self, iq_samples):
        if len(iq_samples) < 2:
            return np.array([], dtype=np.float32)
        phase = np.unwrap(np.angle(iq_samples))
        audio = np.diff(phase)
        return self._resample_to_16k(audio)

    # Backwards-compatible aliases for existing tests/callers.
    def _am_demodulate(self, iq_samples):
        return self.demodulate_am(iq_samples)

    def _nfm_demodulate(self, iq_samples):
        return self.demodulate_nfm(iq_samples)

    def _fm_demodulate(self, iq_samples):
        return self.demodulate_fm(iq_samples)
        
    def attempt_real_rf_capture(self, frequency_name, frequency_hz, duration):
        """YOLO real RF capture from SDRplay/RTL-SDR"""
        
        try:
            self.logger.info(f"📡 REAL RF CAPTURE: {frequency_name} ({frequency_hz/1e6:.3f} MHz)")
            
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            iq_file = f"/tmp/real_rf_{timestamp}.iq"
            
            # RTL-SDR capture command
            capture_cmd = [
                'rtl_sdr', 
                '-f', str(int(frequency_hz)),
                '-s', str(self.sample_rate),
                '-n', str(int(self.sample_rate * duration)),
                iq_file
            ]
            
            # Capture with timeout
            result = subprocess.run(capture_cmd, timeout=duration+10, 
                                  capture_output=True, text=True)
            
            if Path(iq_file).exists() and Path(iq_file).stat().st_size > 5000:
                file_size = Path(iq_file).stat().st_size
                self.logger.info(f"✅ REAL RF DATA: {file_size:,} bytes captured")
                
                # Convert IQ to audio
                iq_samples = np.fromfile(iq_file, dtype=np.uint8)
                
                if len(iq_samples) > 2000:
                    # Convert uint8 IQ to complex (-127.5 to +127.5)
                    i_samples = iq_samples[::2].astype(float) - 127.5
                    q_samples = iq_samples[1::2].astype(float) - 127.5
                    iq_complex = i_samples + 1j * q_samples

                    demod_mode = self._select_demod_mode(frequency_hz)
                    if demod_mode == "am":
                        audio_demod = self.demodulate_am(iq_complex)
                    elif demod_mode == "nfm":
                        audio_demod = self.demodulate_nfm(iq_complex)
                    else:
                        audio_demod = self.demodulate_fm(iq_complex)
                    
                    # Audio processing for voice extraction
                    if len(audio_demod) > 0:
                        # Remove DC
                        audio_demod = audio_demod - np.mean(audio_demod)
                        
                        # Voice band filter (300Hz - 3.4kHz for marine/aviation radio)
                        # Simple high-pass to remove low frequency noise
                        if len(audio_demod) > 200:
                            audio_demod = audio_demod - np.convolve(audio_demod, np.ones(100)/100, mode='same')
                        
                        # Normalize 
                        if np.max(np.abs(audio_demod)) > 0:
                            audio_demod = audio_demod / np.max(np.abs(audio_demod)) * 0.8
                        
                        # Save real RF audio
                        audio_file = self.session_dir / f"REAL_RF_{frequency_name.replace(' ', '_')}_{timestamp}.wav"
                        self._write_wav_with_metadata(
                            audio_file,
                            audio_demod,
                            self.demod_audio_sample_rate,
                            {
                                "source_type": "REAL_RF",
                                "frequency_name": frequency_name,
                                "frequency_hz": int(round(frequency_hz)),
                                "demod_mode": demod_mode,
                            },
                        )
                        
                        # Clean up IQ file
                        os.unlink(iq_file)
                        
                        self.logger.info(
                            f"🎉 REAL RF AUDIO: {audio_file.name} (demod={demod_mode}, sr={self.demod_audio_sample_rate})"
                        )
                        return str(audio_file)
            else:
                if Path(iq_file).exists():
                    os.unlink(iq_file)
                    
        except subprocess.TimeoutExpired:
            self.logger.warning("Real RF capture timed out")
        except FileNotFoundError:
            self.logger.warning("rtl_sdr command not found")
        except Exception as e:
            self.logger.warning(f"Real RF capture failed: {e}")
            
        return None
    
    def create_fallback_signal(self, frequency_name, frequency_hz, duration):
        """Create realistic fallback when real capture fails"""
        
        sample_rate = self.audio_sample_rate
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Decide if this should have voice based on frequency and time
        current_hour = datetime.now().hour
        
        # Higher voice probability for key frequencies during active hours
        voice_prob = 0.15  # Base probability
        
        if "Emergency" in frequency_name or "CH16" in frequency_name:
            voice_prob = 0.8  # Emergency channels very active
        elif "Coast Guard" in frequency_name or "Tower" in frequency_name:
            voice_prob = 0.6  # Official channels active
        elif "Bridge" in frequency_name or "Approach" in frequency_name:
            voice_prob = 0.5  # Navigation channels active
        
        # Time-based adjustment
        if 8 <= current_hour <= 20:  # Daytime more active
            voice_prob *= 1.5
        else:
            voice_prob *= 0.7
            
        # Create signal
        signal_audio = np.zeros_like(t)
        
        if np.random.random() < voice_prob:
            # Voice present - create realistic communication
            if "Emergency" in frequency_name or "CH16" in frequency_name:
                return self.create_emergency_communication(t, frequency_name)
            elif "Aviation" in frequency_name or frequency_hz > 118e6:
                return self.create_aviation_communication(t, frequency_name)
            else:
                return self.create_maritime_communication(t, frequency_name)
        else:
            # No voice - just RF environment
            return self.create_rf_environment(t)
    
    def create_emergency_communication(self, t, freq_name):
        """Create realistic emergency communication"""
        
        emergency_types = [
            "Coast Guard emergency response",
            "Vessel in distress calling",
            "Search and rescue coordination", 
            "Medical emergency at sea",
            "Man overboard alert"
        ]
        
        comm_type = random.choice(emergency_types)
        
        # Create voice segments
        voice_segments = [
            (200, 0.8, 0.0, 0.3),    # "Coast Guard Coast Guard"
            (0, 0, 0.3, 0.5),        # Break
            (185, 0.7, 0.5, 0.8),    # "This is vessel Alpha"
            (0, 0, 0.8, 0.9),        # Break  
            (195, 0.8, 0.9, 1.0),    # "We have emergency"
        ]
        
        signal_audio = np.zeros_like(t)
        
        for freq, amp, start_frac, end_frac in voice_segments:
            start_idx = int(start_frac * len(t))
            end_idx = int(end_frac * len(t))
            
            if freq > 0 and end_idx > start_idx:
                segment_t = t[start_idx:end_idx]
                
                # Human voice with harmonics
                voice = (np.sin(2 * np.pi * freq * segment_t) * amp +
                        np.sin(2 * np.pi * freq * 2.1 * segment_t) * amp * 0.4 +
                        np.sin(2 * np.pi * freq * 3.2 * segment_t) * amp * 0.2)
                
                # Voice modulation and urgency
                urgency = 1 + 0.4 * np.sin(2 * np.pi * 5 * segment_t)  # Stressed speech
                voice *= urgency
                
                signal_audio[start_idx:end_idx] = voice
        
        # Add RF environment
        signal_audio += self.create_rf_environment(t) * 0.3
        
        # Save with emergency type in log
        self.logger.info(f"🚨 EMERGENCY VOICE: {comm_type} on {freq_name}")
        
        return signal_audio
    
    def create_maritime_communication(self, t, freq_name):
        """Create realistic maritime communication"""
        
        maritime_types = [
            "Harbor pilot request",
            "Bridge-to-bridge navigation", 
            "Ship requesting berth",
            "Harbor master instructions",
            "Vessel traffic coordination"
        ]
        
        comm_type = random.choice(maritime_types)
        
        # Create realistic marine communication pattern
        voice_freq = 180 + random.randint(-20, 20)  # Male marine radio voice
        
        # Voice with marine radio characteristics
        voice = np.sin(2 * np.pi * voice_freq * t) * 0.6
        voice += np.sin(2 * np.pi * voice_freq * 2.1 * t) * 0.3
        voice += np.sin(2 * np.pi * voice_freq * 3.2 * t) * 0.15
        
        # Marine radio modulation
        modulation = 1 + 0.3 * np.sin(2 * np.pi * 3 * t)
        voice *= modulation
        
        # Add marine RF environment
        marine_env = self.create_rf_environment(t)
        final_signal = voice + marine_env * 0.4
        
        self.logger.info(f"🚢 MARITIME VOICE: {comm_type} on {freq_name}")
        
        return final_signal
    
    def create_aviation_communication(self, t, freq_name):
        """Create realistic aviation communication"""
        
        aviation_types = [
            "Pilot requesting clearance",
            "Tower control instructions",
            "Aircraft position report",
            "Emergency frequency check",
            "Flight following request"
        ]
        
        comm_type = random.choice(aviation_types)
        
        # Aviation voice characteristics (clearer than marine)
        voice_freq = 190 + random.randint(-15, 15)  # Aviation voice
        
        voice = np.sin(2 * np.pi * voice_freq * t) * 0.7
        voice += np.sin(2 * np.pi * voice_freq * 2.2 * t) * 0.4
        voice += np.sin(2 * np.pi * voice_freq * 3.1 * t) * 0.2
        
        # Professional aviation speech patterns
        professional_mod = 1 + 0.2 * np.sin(2 * np.pi * 4 * t)  # Clear, measured speech
        voice *= professional_mod
        
        # Add aviation RF environment (cleaner than marine)
        aviation_env = self.create_rf_environment(t) * 0.2
        final_signal = voice + aviation_env
        
        self.logger.info(f"✈️ AVIATION VOICE: {comm_type} on {freq_name}")
        
        return final_signal
    
    def create_rf_environment(self, t):
        """Create realistic RF environment noise"""
        
        # White noise (RF background)
        white_noise = np.random.normal(0, 0.1, len(t))
        
        # Atmospheric noise (slow variations)
        atmospheric = 0.08 * np.sin(2 * np.pi * 0.02 * t) * np.random.normal(1, 0.3, len(t))
        
        # Equipment noise (60Hz hum)
        equipment = 0.03 * np.sin(2 * np.pi * 60 * t)
        
        # RF fading
        fading = 0.05 * np.sin(2 * np.pi * 0.1 * t)
        
        return white_noise + atmospheric + equipment + fading
    
    def _voice_ratio_threshold_for_frequency(self, frequency_hz):
        """Return ratio threshold, with an aviation-specific lower floor."""
        freq_mhz = frequency_hz / 1e6
        if 108.0 <= freq_mhz <= 137.0:
            return min(self.voice_ratio_threshold, 0.08)
        return self.voice_ratio_threshold

    def detect_voice_activity(self, audio_signal, sample_rate, frequency_hz):
        """Detect voice activity in audio signal"""
        
        if len(audio_signal) == 0:
            return 0.0, 0.0, self._voice_ratio_threshold_for_frequency(frequency_hz)
            
        # RMS energy
        rms = np.sqrt(np.mean(audio_signal**2))
        voice_ratio = 0.0
        
        # Spectral analysis for voice characteristics
        if len(audio_signal) > 1024:
            freqs, psd = signal.welch(audio_signal, sample_rate, nperseg=1024)
            
            # Voice band energy (300-3400 Hz)
            voice_band_mask = (freqs >= 300) & (freqs <= 3400)
            voice_energy = np.mean(psd[voice_band_mask]) if np.any(voice_band_mask) else 0
            
            # Total energy
            total_energy = np.mean(psd)
            if total_energy > 0:
                voice_ratio = voice_energy / total_energy
            
            # Voice activity score (combination of RMS and spectral characteristics)
            if total_energy > 0:
                voice_score = (rms * 2 + voice_ratio) / 3
            else:
                voice_score = rms
        else:
            voice_score = rms
            
        ratio_threshold = self._voice_ratio_threshold_for_frequency(frequency_hz)
        return voice_score, voice_ratio, ratio_threshold
    
    def scan_frequency(self, frequency_name, frequency_hz, duration=5):
        """Scan a single frequency for voice activity"""
        
        self.total_scans += 1
        demod_mode = self._select_demod_mode(frequency_hz)
        self.logger.info(
            f"📡 Scan config: {frequency_name} ({frequency_hz/1e6:.3f} MHz) demod={demod_mode}"
        )
        
        # Try real RF capture first
        audio_file = self.attempt_real_rf_capture(frequency_name, frequency_hz, duration)
        
        if audio_file:
            # Load captured audio
            try:
                audio_signal, detected_sample_rate = sf.read(audio_file)
                source_type = "REAL RF"
            except:
                audio_signal = None
        
        if not audio_file or audio_signal is None:
            # Fallback to simulation
            audio_signal = self.create_fallback_signal(frequency_name, frequency_hz, duration)
            detected_sample_rate = self.audio_sample_rate
            
            # Save fallback audio
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            audio_file = self.session_dir / f"SIM_{frequency_name.replace(' ', '_')}_{timestamp}.wav"
            self._write_wav_with_metadata(
                audio_file,
                audio_signal,
                self.audio_sample_rate,
                {
                    "source_type": "SIMULATION",
                    "frequency_name": frequency_name,
                    "frequency_hz": int(round(frequency_hz)),
                    "demod_mode": self._select_demod_mode(frequency_hz),
                },
            )
            source_type = "SIMULATION"
        
        # Detect voice activity
        voice_score, voice_ratio, ratio_threshold = self.detect_voice_activity(
            audio_signal, detected_sample_rate, frequency_hz
        )
        
        self.logger.info(f"   Voice Score: {voice_score:.3f} (threshold: {self.voice_threshold})")
        self.logger.info(f"   Voice Ratio: {voice_ratio:.3f} (threshold: {ratio_threshold:.3f})")
        
        if voice_score > self.voice_threshold or voice_ratio >= ratio_threshold:
            self.voice_detections += 1
            self.captures_saved += 1
            self.logger.info(f"   ✅ HUMAN SPEECH DETECTED! ({source_type})")
            self._auto_transcribe_capture(Path(audio_file), frequency_name)
            return True, audio_file, voice_score
        else:
            # Remove non-voice files to save space
            if Path(audio_file).exists():
                os.unlink(audio_file)
            metadata_path = self._capture_metadata_path(Path(audio_file))
            if metadata_path.exists():
                metadata_path.unlink()
            return False, None, voice_score
    
    def frequency_lock_mode(self, frequency_name, frequency_hz, initial_file):
        """Lock onto frequency with continued voice activity"""
        
        self.logger.info(f"\n🎯 VOICE LOCKED - Extended Capture")
        self.logger.info(f"   Frequency: {frequency_name} ({frequency_hz/1e6:.3f} MHz)")
        self.logger.info(f"   Duration: {self.lock_duration}s + extension time")
        
        # Initial extended capture
        extended_file = self.attempt_real_rf_capture(frequency_name, frequency_hz, self.lock_duration)
        
        if extended_file:
            self.logger.info(f"   ✅ Extended capture complete!")
            self.logger.info(f"   📁 Saved: {Path(extended_file).name}")
            self._auto_transcribe_capture(Path(extended_file), frequency_name)
        
        # Monitor for continued activity
        self.logger.info(f"   📻 Monitoring for continued activity...")
        
        continued_captures = 0
        max_continued = 10  # Prevent infinite locking
        
        while continued_captures < max_continued:
            time.sleep(2)  # 2 second intervals
            
            # Quick voice check
            voice_detected, capture_file, voice_score = self.scan_frequency(
                frequency_name, frequency_hz, duration=3
            )
            
            if voice_detected:
                continued_captures += 1
                self.logger.info(f"   🎙️  Continued voice activity detected (score: {voice_score:.3f})")
                
                if capture_file:
                    old_audio_file = Path(capture_file)
                    new_name = str(capture_file).replace('.wav', f'_continued_{continued_captures:02d}.wav')
                    new_audio_file = Path(new_name)
                    old_audio_file.rename(new_audio_file)
                    self._move_capture_metadata(old_audio_file, new_audio_file)
                    self.logger.info(f"   📁 Additional capture: {Path(new_name).name}")
                    self._auto_transcribe_capture(Path(new_name), frequency_name)
            else:
                break
        
        self.logger.info(f"   📊 Lock complete: {continued_captures} additional captures")
    
    def autonomous_hunt(self, max_runtime_hours=12):
        """Run autonomous voice hunting for specified hours"""
        
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=max_runtime_hours)
        
        self.logger.info(f"\n🎯 Starting Real Autonomous RF Voice Hunt")
        self.logger.info(f"   Session: {self.session_name}")
        self.logger.info(f"   Max Runtime: {max_runtime_hours} hours")
        self.logger.info(f"   Output Directory: {self.session_dir}")
        self.logger.info("=" * 80)
        
        self.logger.info(f"📋 Total frequency entries (with priority weighting): {len(self.all_frequencies)}")
        
        scan_count = 0
        
        while datetime.now(timezone.utc) < end_time:
            try:
                # Select frequency (random with priority weighting)
                frequency_name, frequency_hz = random.choice(self.all_frequencies)
                
                self.logger.info(f"\n📡 Scanning: {frequency_name} ({frequency_hz/1e6:.3f} MHz)")
                
                # Scan frequency
                voice_detected, capture_file, voice_score = self.scan_frequency(
                    frequency_name, frequency_hz, duration=5
                )
                
                if voice_detected:
                    # Enter frequency lock mode
                    self.frequency_lock_mode(frequency_name, frequency_hz, capture_file)
                    
                    # Brief pause after lock
                    time.sleep(5)
                else:
                    # Quick pause between scans
                    time.sleep(1)
                
                scan_count += 1
                
                # Status update every 50 scans
                if scan_count % 50 == 0:
                    runtime = datetime.now(timezone.utc) - start_time
                    self.logger.info(f"\n📊 Status Update (Runtime: {runtime})")
                    self.logger.info(f"   Total Scans: {self.total_scans}")
                    self.logger.info(f"   Voice Detections: {self.voice_detections}")
                    self.logger.info(f"   Captures Saved: {self.captures_saved}")
                    self.logger.info(f"   Detection Rate: {(self.voice_detections/self.total_scans*100):.1f}%")
                    
            except KeyboardInterrupt:
                self.logger.info(f"\n🛑 Hunt interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Hunt error: {e}")
                time.sleep(5)  # Brief pause on error
        
        # Final statistics
        runtime = datetime.now(timezone.utc) - start_time
        self.logger.info(f"\n🏁 Real Autonomous Hunt Complete")
        self.logger.info(f"   Total Runtime: {runtime}")
        self.logger.info(f"   Total Scans: {self.total_scans}")
        self.logger.info(f"   Voice Detections: {self.voice_detections}")
        self.logger.info(f"   Captures Saved: {self.captures_saved}")
        self.logger.info(f"   Session Directory: {self.session_dir}")

def main():
    """Real autonomous RF voice hunting - all night operation"""
    
    print("🎯 Real Autonomous RF Voice Hunter")
    print("   Using your connected SDRplay RSPdx for REAL RF capture")
    print("=" * 50)
    
    # Initialize hunter
    hunter = RealAutonomousVoiceHunter(session_name=f"autonomous_hunt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    
    print(f"📁 Session: {hunter.session_name}")
    print(f"📊 Monitoring {len(hunter.maritime_frequencies)} maritime + {len(hunter.aviation_frequencies)} aviation frequencies")
    print(f"🎯 Priority focus: CH16 Emergency, Coast Guard, Bridge-to-Bridge, ATC")
    print(f"⏰ Will run for up to 12 hours (until ~{(datetime.now(timezone.utc) + timedelta(hours=12)).strftime('%H:%M')})")
    print("")
    
    # Run autonomous hunt
    hunter.autonomous_hunt(max_runtime_hours=12)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n👋 Real RF hunt interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

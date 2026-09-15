#!/usr/bin/env python3
"""
Voice Quality Inspector
Analyzes all captured audio files to identify which ones actually contain voice
Saves you from processing 18,000 files through ElevenLabs!
"""

import numpy as np
import soundfile as sf
from pathlib import Path
import json
from datetime import datetime, timezone
import logging
from scipy import signal
from scipy.fft import fft
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import threading
from tqdm import tqdm

class VoiceQualityInspector:
    """Advanced voice quality analysis for RF captures"""
    
    def __init__(self, capture_dir):
        self.capture_dir = Path(capture_dir)
        self.results = []
        self.lock = threading.Lock()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO,
                          format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
    def advanced_voice_detection(self, audio_file):
        """Advanced multi-parameter voice detection"""
        
        try:
            # Load audio
            audio, sample_rate = sf.read(str(audio_file))
            
            if len(audio) == 0:
                return {
                    'file': audio_file.name,
                    'has_voice': False,
                    'confidence': 0.0,
                    'reasons': ['empty_file'],
                    'duration': 0.0,
                    'rms_energy': 0.0,
                    'voice_band_ratio': 0.0,
                    'spectral_centroid': 0.0,
                    'zero_crossing_rate': 0.0,
                    'voice_probability': 0.0
                }
            
            duration = len(audio) / sample_rate
            
            # 1. RMS Energy Analysis
            rms_energy = np.sqrt(np.mean(audio**2))
            
            # 2. Spectral Analysis
            if len(audio) > 1024:
                freqs, psd = signal.welch(audio, sample_rate, nperseg=1024)
                
                # Voice band (300-3400 Hz) vs total energy
                voice_band_mask = (freqs >= 300) & (freqs <= 3400)
                voice_band_energy = np.sum(psd[voice_band_mask])
                total_energy = np.sum(psd)
                voice_band_ratio = voice_band_energy / total_energy if total_energy > 0 else 0
                
                # Spectral centroid (brightness measure)
                spectral_centroid = np.sum(freqs * psd) / np.sum(psd) if np.sum(psd) > 0 else 0
                
            else:
                voice_band_ratio = 0
                spectral_centroid = 0
            
            # 3. Zero Crossing Rate (voice vs noise characteristic)
            zero_crossings = np.where(np.diff(np.sign(audio)))[0]
            zero_crossing_rate = len(zero_crossings) / len(audio) if len(audio) > 0 else 0
            
            # 4. Formant Analysis (human voice has specific formant patterns)
            formant_score = self.analyze_formants(audio, sample_rate)
            
            # 5. Modulation Detection (human speech has ~4-8 Hz modulation)
            modulation_score = self.detect_voice_modulation(audio, sample_rate)
            
            # 6. Harmonicity (voice has harmonic structure)
            harmonicity = self.analyze_harmonicity(audio, sample_rate)
            
            # 7. Dynamic Range (voice varies more than constant tones)
            dynamic_range = np.max(audio) - np.min(audio) if len(audio) > 0 else 0
            
            # Combined Voice Probability Score
            voice_probability = self.calculate_voice_probability(
                rms_energy, voice_band_ratio, spectral_centroid, 
                zero_crossing_rate, formant_score, modulation_score, 
                harmonicity, dynamic_range
            )
            
            # Decision Logic
            has_voice = voice_probability > 0.6  # Higher threshold for quality
            confidence = voice_probability
            
            # Detailed reasons
            reasons = []
            if rms_energy < 0.01:
                reasons.append('low_energy')
            if voice_band_ratio < 0.3:
                reasons.append('poor_voice_band')
            if spectral_centroid < 500 or spectral_centroid > 4000:
                reasons.append('wrong_frequency_range')
            if zero_crossing_rate > 0.3:
                reasons.append('too_noisy')
            if formant_score < 0.3:
                reasons.append('no_formants')
            if modulation_score < 0.2:
                reasons.append('no_voice_modulation')
            if harmonicity < 0.2:
                reasons.append('not_harmonic')
            if dynamic_range < 0.1:
                reasons.append('no_variation')
            
            if not reasons:
                reasons.append('good_voice_candidate')
                
            return {
                'file': audio_file.name,
                'has_voice': has_voice,
                'confidence': confidence,
                'reasons': reasons,
                'duration': duration,
                'rms_energy': float(rms_energy),
                'voice_band_ratio': float(voice_band_ratio),
                'spectral_centroid': float(spectral_centroid),
                'zero_crossing_rate': float(zero_crossing_rate),
                'formant_score': float(formant_score),
                'modulation_score': float(modulation_score),
                'harmonicity': float(harmonicity),
                'dynamic_range': float(dynamic_range),
                'voice_probability': float(voice_probability)
            }
            
        except Exception as e:
            return {
                'file': audio_file.name,
                'has_voice': False,
                'confidence': 0.0,
                'reasons': [f'error: {str(e)}'],
                'duration': 0.0,
                'rms_energy': 0.0,
                'voice_band_ratio': 0.0,
                'spectral_centroid': 0.0,
                'zero_crossing_rate': 0.0,
                'voice_probability': 0.0
            }
    
    def analyze_formants(self, audio, sample_rate):
        """Detect formant-like structures (human voice characteristic)"""
        
        try:
            if len(audio) < 2048:
                return 0.0
                
            # FFT analysis
            window_size = 2048
            overlap = window_size // 2
            
            formant_scores = []
            
            for i in range(0, len(audio) - window_size, overlap):
                window = audio[i:i+window_size]
                
                # Apply window function
                window = window * np.hanning(len(window))
                
                # FFT
                spectrum = np.abs(fft(window))
                freqs = np.fft.fftfreq(len(spectrum), 1/sample_rate)
                
                # Focus on positive frequencies up to 4000 Hz
                pos_mask = (freqs >= 0) & (freqs <= 4000)
                spectrum = spectrum[pos_mask]
                freqs = freqs[pos_mask]
                
                # Look for formant-like peaks
                # Human speech typically has formants at ~700Hz, ~1200Hz, ~2500Hz
                formant_regions = [
                    (600, 900),   # F1
                    (900, 1500),  # F2  
                    (2000, 3000)  # F3
                ]
                
                peak_count = 0
                for f_min, f_max in formant_regions:
                    region_mask = (freqs >= f_min) & (freqs <= f_max)
                    if np.any(region_mask):
                        region_spectrum = spectrum[region_mask]
                        if len(region_spectrum) > 0:
                            peak_power = np.max(region_spectrum)
                            avg_power = np.mean(spectrum)
                            if peak_power > avg_power * 2:  # Peak is 2x average
                                peak_count += 1
                
                formant_score = peak_count / len(formant_regions)
                formant_scores.append(formant_score)
            
            return np.mean(formant_scores) if formant_scores else 0.0
            
        except:
            return 0.0
    
    def detect_voice_modulation(self, audio, sample_rate):
        """Detect 4-8Hz modulation typical of human speech"""
        
        try:
            if len(audio) < sample_rate:  # Need at least 1 second
                return 0.0
            
            # Envelope detection
            envelope = np.abs(signal.hilbert(audio))
            
            # Smooth the envelope
            envelope = signal.savgol_filter(envelope, min(51, len(envelope)//10 | 1), 3)
            
            # FFT of envelope to find modulation frequencies
            envelope_fft = np.abs(fft(envelope))
            mod_freqs = np.fft.fftfreq(len(envelope_fft), 1/sample_rate)
            
            # Look for modulation in 2-10 Hz range (speech range)
            mod_mask = (mod_freqs >= 2) & (mod_freqs <= 10)
            if np.any(mod_mask):
                speech_mod_power = np.sum(envelope_fft[mod_mask])
                total_mod_power = np.sum(envelope_fft[mod_freqs >= 0])
                
                return speech_mod_power / total_mod_power if total_mod_power > 0 else 0
            
            return 0.0
            
        except:
            return 0.0
    
    def analyze_harmonicity(self, audio, sample_rate):
        """Measure harmonicity (voice has harmonic structure)"""
        
        try:
            if len(audio) < 2048:
                return 0.0
            
            # Autocorrelation for pitch detection
            autocorr = np.correlate(audio, audio, mode='full')
            autocorr = autocorr[autocorr.size // 2:]
            
            # Look for periodic patterns (harmonicity)
            # Remove first peak (always maximum at lag 0)
            if len(autocorr) > 100:
                autocorr = autocorr[50:]  # Skip first 50 samples
                
                # Find peaks
                peaks, _ = signal.find_peaks(autocorr, height=np.max(autocorr) * 0.3)
                
                if len(peaks) > 0:
                    # Harmonicity is related to peak strength
                    peak_values = autocorr[peaks]
                    harmonicity = np.mean(peak_values) / np.max(autocorr) if np.max(autocorr) > 0 else 0
                    return min(harmonicity, 1.0)
            
            return 0.0
            
        except:
            return 0.0
    
    def calculate_voice_probability(self, rms_energy, voice_band_ratio, spectral_centroid, 
                                  zero_crossing_rate, formant_score, modulation_score, 
                                  harmonicity, dynamic_range):
        """Calculate overall voice probability"""
        
        score = 0.0
        
        # Energy check (voice needs sufficient energy)
        if rms_energy > 0.05:
            score += 0.15
        elif rms_energy > 0.02:
            score += 0.1
        
        # Voice band ratio (voice energy should be in 300-3400Hz)
        if voice_band_ratio > 0.6:
            score += 0.2
        elif voice_band_ratio > 0.4:
            score += 0.15
        elif voice_band_ratio > 0.2:
            score += 0.1
        
        # Spectral centroid (voice typically 1000-3000 Hz)
        if 1000 <= spectral_centroid <= 3000:
            score += 0.15
        elif 800 <= spectral_centroid <= 4000:
            score += 0.1
        
        # Zero crossing rate (voice has moderate ZCR)
        if 0.05 <= zero_crossing_rate <= 0.2:
            score += 0.1
        elif zero_crossing_rate <= 0.05:
            score += 0.05
        
        # Formant score
        score += formant_score * 0.15
        
        # Modulation score  
        score += modulation_score * 0.1
        
        # Harmonicity
        score += harmonicity * 0.1
        
        # Dynamic range (voice varies)
        if dynamic_range > 0.5:
            score += 0.05
        
        return min(score, 1.0)
    
    def process_files(self, max_workers=8, sample_size=None):
        """Process all audio files with parallel processing"""
        
        # Get all wav files
        wav_files = list(self.capture_dir.glob("*.wav"))
        
        if sample_size:
            # Random sample for testing
            import random
            wav_files = random.sample(wav_files, min(sample_size, len(wav_files)))
        
        self.logger.info(f"Processing {len(wav_files)} audio files...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Use tqdm for progress bar
            results = list(tqdm(
                executor.map(self.advanced_voice_detection, wav_files),
                total=len(wav_files),
                desc="Analyzing voice quality"
            ))
        
        self.results = results
        return results
    
    def generate_report(self, output_file=None):
        """Generate comprehensive analysis report"""
        
        if not self.results:
            self.logger.error("No results to report. Run process_files() first.")
            return
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(self.results)
        
        # Summary statistics
        total_files = len(df)
        voice_files = len(df[df['has_voice'] == True])
        no_voice_files = total_files - voice_files
        
        high_confidence_voice = len(df[df['confidence'] > 0.8])
        medium_confidence_voice = len(df[(df['confidence'] > 0.6) & (df['confidence'] <= 0.8)])
        low_confidence_voice = len(df[(df['confidence'] > 0.4) & (df['confidence'] <= 0.6)])
        
        # Quality tiers
        excellent_voice = df[df['confidence'] > 0.9]
        good_voice = df[(df['confidence'] > 0.7) & (df['confidence'] <= 0.9)]
        fair_voice = df[(df['confidence'] > 0.5) & (df['confidence'] <= 0.7)]
        
        report = f"""
🎙️ VOICE QUALITY ANALYSIS REPORT
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
================================

📊 SUMMARY STATISTICS:
• Total Files Analyzed: {total_files:,}
• Files with Voice: {voice_files:,} ({voice_files/total_files*100:.1f}%)
• Files without Voice: {no_voice_files:,} ({no_voice_files/total_files*100:.1f}%)

🎯 CONFIDENCE BREAKDOWN:
• High Confidence (>80%): {high_confidence_voice:,} files
• Medium Confidence (60-80%): {medium_confidence_voice:,} files  
• Low Confidence (40-60%): {low_confidence_voice:,} files

⭐ QUALITY TIERS:
• EXCELLENT (>90% confidence): {len(excellent_voice):,} files - Process with ElevenLabs FIRST
• GOOD (70-90% confidence): {len(good_voice):,} files - High priority for processing
• FAIR (50-70% confidence): {len(fair_voice):,} files - Review manually

💰 COST SAVINGS:
• Original: {total_files:,} files to process
• Recommended: {len(df[df['confidence'] > 0.7]):,} files (excellent + good)
• Savings: {total_files - len(df[df['confidence'] > 0.7]):,} files ({(total_files - len(df[df['confidence'] > 0.7]))/total_files*100:.1f}% cost reduction)

📈 TECHNICAL METRICS:
• Average Voice Probability: {df['voice_probability'].mean():.3f}
• Average RMS Energy: {df['rms_energy'].mean():.3f}
• Average Voice Band Ratio: {df['voice_band_ratio'].mean():.3f}
• Average Spectral Centroid: {df['spectral_centroid'].mean():.0f} Hz

🔍 COMMON ISSUES:
"""
        
        # Analyze common rejection reasons
        all_reasons = []
        for reasons in df['reasons']:
            all_reasons.extend(reasons)
        
        from collections import Counter
        reason_counts = Counter(all_reasons)
        
        for reason, count in reason_counts.most_common(5):
            report += f"• {reason.replace('_', ' ').title()}: {count:,} files\n"
        
        # Top files recommendations
        report += f"\n🏆 TOP RECOMMENDED FILES FOR ELEVENLABS:\n"
        top_files = df.nlargest(10, 'confidence')
        for idx, row in top_files.iterrows():
            report += f"• {row['file']} (confidence: {row['confidence']:.3f})\n"
        
        print(report)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            self.logger.info(f"Report saved to {output_file}")
        
        # Save detailed results
        csv_file = output_file.replace('.txt', '_detailed.csv') if output_file else 'voice_analysis_detailed.csv'
        df.to_csv(csv_file, index=False)
        self.logger.info(f"Detailed results saved to {csv_file}")
        
        return df

def main():
    """Run voice quality inspection on captured files"""
    
    capture_dir = "rf_captures/autonomous_hunt_20250911_212457"
    
    print("🎙️ Voice Quality Inspector")
    print("=" * 50)
    
    inspector = VoiceQualityInspector(capture_dir)
    
    # Process files (start with sample for speed)
    print("🔍 Running advanced voice detection on audio files...")
    results = inspector.process_files(max_workers=8, sample_size=1000)  # Sample 1000 files first
    
    # Generate report
    print("\n📊 Generating analysis report...")
    df = inspector.generate_report('voice_quality_report.txt')
    
    print(f"\n✅ Analysis complete! Check voice_quality_report.txt for details.")
    
    return df

if __name__ == "__main__":
    df = main()
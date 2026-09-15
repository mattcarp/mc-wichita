#!/usr/bin/env python3
"""
Fast Voice Inspector - Quick analysis to separate voice from non-voice
Optimized for speed to process 18,000+ files efficiently
"""

import numpy as np
import soundfile as sf
from pathlib import Path
import json
from datetime import datetime, timezone
from scipy import signal
import random

class FastVoiceInspector:
    """Fast voice detection for large batches"""
    
    def __init__(self, capture_dir):
        self.capture_dir = Path(capture_dir)
        
    def quick_voice_check(self, audio_file):
        """Ultra-fast voice detection using key indicators"""
        
        try:
            # Load audio
            audio, sample_rate = sf.read(str(audio_file))
            
            if len(audio) == 0:
                return {
                    'file': audio_file.name,
                    'has_voice': False,
                    'score': 0.0,
                    'reason': 'empty_file'
                }
            
            # 1. RMS Energy (quick power check)
            rms = np.sqrt(np.mean(audio**2))
            if rms < 0.01:  # Too quiet
                return {
                    'file': audio_file.name,
                    'has_voice': False,
                    'score': rms,
                    'reason': 'too_quiet'
                }
            
            # 2. Quick spectral analysis (voice band check)
            if len(audio) > 1024:
                # Simple FFT
                fft_result = np.abs(np.fft.fft(audio[:1024]))
                freqs = np.fft.fftfreq(1024, 1/sample_rate)
                
                # Voice band (300-3400 Hz)
                voice_mask = (freqs >= 300) & (freqs <= 3400) & (freqs >= 0)
                total_mask = freqs >= 0
                
                voice_energy = np.sum(fft_result[voice_mask])
                total_energy = np.sum(fft_result[total_mask])
                
                voice_ratio = voice_energy / total_energy if total_energy > 0 else 0
                
                if voice_ratio < 0.2:  # Less than 20% in voice band
                    return {
                        'file': audio_file.name,
                        'has_voice': False,
                        'score': voice_ratio,
                        'reason': 'wrong_frequency_content'
                    }
            else:
                voice_ratio = 0.5  # Assume OK if too short to analyze
            
            # 3. Dynamic range check (voice varies, constant tones don't)
            dynamic_range = np.max(audio) - np.min(audio)
            if dynamic_range < 0.1:
                return {
                    'file': audio_file.name,
                    'has_voice': False,
                    'score': dynamic_range,
                    'reason': 'no_variation'
                }
            
            # 4. Zero crossing rate (moderate for voice)
            zero_crossings = len(np.where(np.diff(np.sign(audio)))[0])
            zcr = zero_crossings / len(audio)
            
            if zcr > 0.4:  # Too noisy/chaotic
                return {
                    'file': audio_file.name,
                    'has_voice': False,
                    'score': zcr,
                    'reason': 'too_noisy'
                }
            
            # Combined score
            voice_score = (rms * 2 + voice_ratio + dynamic_range + (0.2 - abs(zcr - 0.1)) * 2) / 6
            
            return {
                'file': audio_file.name,
                'has_voice': voice_score > 0.3,  # Lower threshold for real data
                'score': float(voice_score),
                'reason': 'potential_voice' if voice_score > 0.3 else 'likely_not_voice',
                'rms': float(rms),
                'voice_ratio': float(voice_ratio),
                'dynamic_range': float(dynamic_range),
                'zcr': float(zcr)
            }
            
        except Exception as e:
            return {
                'file': audio_file.name,
                'has_voice': False,
                'score': 0.0,
                'reason': f'error: {str(e)}'
            }
    
    def sample_analysis(self, sample_size=100):
        """Analyze a random sample to understand the data"""
        
        print(f"🎯 Analyzing random sample of {sample_size} files...")
        
        wav_files = list(self.capture_dir.glob("*.wav"))
        if len(wav_files) == 0:
            print("❌ No WAV files found!")
            return
        
        # Random sample
        sample_files = random.sample(wav_files, min(sample_size, len(wav_files)))
        
        results = []
        voice_count = 0
        
        for i, audio_file in enumerate(sample_files):
            if i % 10 == 0:
                print(f"   Progress: {i}/{len(sample_files)}")
            
            result = self.quick_voice_check(audio_file)
            results.append(result)
            
            if result['has_voice']:
                voice_count += 1
        
        # Analysis
        print(f"\n📊 SAMPLE ANALYSIS RESULTS:")
        print(f"   Total Sampled: {len(results)}")
        print(f"   Detected Voice: {voice_count} ({voice_count/len(results)*100:.1f}%)")
        print(f"   No Voice: {len(results)-voice_count} ({(len(results)-voice_count)/len(results)*100:.1f}%)")
        
        # Show examples
        voice_files = [r for r in results if r['has_voice']]
        no_voice_files = [r for r in results if not r['has_voice']]
        
        if voice_files:
            print(f"\n✅ TOP VOICE CANDIDATES:")
            voice_files.sort(key=lambda x: x['score'], reverse=True)
            for i, f in enumerate(voice_files[:5]):
                print(f"   {i+1}. {f['file']} (score: {f['score']:.3f})")
        
        if no_voice_files:
            print(f"\n❌ COMMON REJECTION REASONS:")
            reasons = {}
            for f in no_voice_files:
                reason = f['reason']
                reasons[reason] = reasons.get(reason, 0) + 1
            
            for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
                print(f"   {reason}: {count} files")
        
        # Extrapolation
        total_files = len(wav_files)
        estimated_voice = int(total_files * (voice_count / len(results)))
        estimated_no_voice = total_files - estimated_voice
        
        print(f"\n🔮 EXTRAPOLATION TO ALL FILES:")
        print(f"   Total Files: {total_files:,}")
        print(f"   Estimated Voice Files: {estimated_voice:,}")
        print(f"   Estimated Non-Voice: {estimated_no_voice:,}")
        print(f"   Potential Cost Savings: {estimated_no_voice/total_files*100:.1f}%")
        
        return results
    
    def quick_filter(self, threshold=0.3, output_file="voice_filtered_list.txt"):
        """Quick filter to identify likely voice files"""
        
        print(f"🚀 Quick filtering all files (threshold: {threshold})...")
        
        wav_files = list(self.capture_dir.glob("*.wav"))
        print(f"   Found {len(wav_files):,} WAV files")
        
        voice_files = []
        processed = 0
        
        for audio_file in wav_files:
            processed += 1
            if processed % 1000 == 0:
                print(f"   Processed: {processed:,}/{len(wav_files):,}")
            
            result = self.quick_voice_check(audio_file)
            
            if result['has_voice'] and result['score'] > threshold:
                voice_files.append(result)
        
        # Sort by score
        voice_files.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"\n✅ FILTERING COMPLETE:")
        print(f"   Total Files: {len(wav_files):,}")
        print(f"   Voice Files Found: {len(voice_files):,}")
        print(f"   Filtered Out: {len(wav_files) - len(voice_files):,}")
        print(f"   Cost Reduction: {(len(wav_files) - len(voice_files))/len(wav_files)*100:.1f}%")
        
        # Save results
        with open(output_file, 'w') as f:
            f.write(f"# Voice Files Filtered List\n")
            f.write(f"# Generated: {datetime.now(timezone.utc)}\n")
            f.write(f"# Total Files: {len(wav_files):,}\n")
            f.write(f"# Voice Files: {len(voice_files):,}\n")
            f.write(f"# Threshold: {threshold}\n\n")
            
            for result in voice_files:
                f.write(f"{result['file']}\t{result['score']:.3f}\t{result.get('rms', 0):.3f}\n")
        
        print(f"📁 Voice file list saved to: {output_file}")
        
        # Show top files
        print(f"\n🏆 TOP 10 VOICE CANDIDATES:")
        for i, result in enumerate(voice_files[:10]):
            print(f"   {i+1}. {result['file']} (score: {result['score']:.3f})")
        
        return voice_files

def main():
    """Quick voice analysis"""
    
    capture_dir = "rf_captures/autonomous_hunt_20250911_212457"
    
    print("⚡ Fast Voice Inspector")
    print("=" * 50)
    
    inspector = FastVoiceInspector(capture_dir)
    
    # First, do a sample analysis
    print("🔬 Step 1: Sample Analysis")
    sample_results = inspector.sample_analysis(sample_size=200)
    
    # Based on sample, do full filtering
    print(f"\n🎯 Step 2: Full Dataset Filtering")
    voice_files = inspector.quick_filter(threshold=0.25)  # Lower threshold based on sample
    
    print(f"\n✅ Analysis Complete!")
    print(f"📊 Recommended for ElevenLabs: {len(voice_files):,} files")
    print(f"💰 Estimated cost savings: {100 - (len(voice_files)/18000*100):.1f}%")
    
    return voice_files

if __name__ == "__main__":
    voice_files = main()
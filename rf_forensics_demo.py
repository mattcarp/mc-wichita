#!/usr/bin/env python3
"""
RF Digital Forensics Toolkit - Complete Pipeline Demo
Demonstrates the end-to-end voice isolation and analysis workflow
"""

import os
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from datetime import datetime, timezone

class RFForensicsDemo:
    def __init__(self):
        self.capture_dir = Path("rf_captures/autonomous_hunt_20250911_212457")
        self.output_dir = Path("rf_forensics_demo_results")
        self.output_dir.mkdir(exist_ok=True)
        
    def analyze_sample(self, audio_file):
        """Comprehensive analysis of an RF audio sample"""
        
        try:
            audio, sample_rate = sf.read(str(audio_file))
            
            # Basic metrics
            duration = len(audio) / sample_rate
            rms = np.sqrt(np.mean(audio**2))
            peak = np.max(np.abs(audio))
            dynamic_range = np.max(audio) - np.min(audio)
            
            # Spectral analysis
            if len(audio) > 1024:
                fft_result = np.abs(np.fft.fft(audio[:2048]))
                freqs = np.fft.fftfreq(2048, 1/sample_rate)
                
                # Voice band analysis (300-3400 Hz)
                voice_mask = (freqs >= 300) & (freqs <= 3400) & (freqs >= 0)
                total_mask = freqs >= 0
                
                voice_energy = np.sum(fft_result[voice_mask])
                total_energy = np.sum(fft_result[total_mask])
                voice_ratio = voice_energy / total_energy if total_energy > 0 else 0
                
                # Find dominant frequency
                max_freq_idx = np.argmax(fft_result[freqs >= 0])
                dominant_freq = freqs[freqs >= 0][max_freq_idx]
            else:
                voice_ratio = 0
                dominant_freq = 0
            
            # Zero crossing rate (voice characteristic)
            zero_crossings = np.sum(np.diff(np.sign(audio)) != 0)
            zcr = zero_crossings / len(audio)
            
            return {
                'filename': audio_file.name,
                'duration': duration,
                'sample_rate': sample_rate,
                'rms_energy': rms,
                'peak_amplitude': peak,
                'dynamic_range': dynamic_range,
                'voice_band_ratio': voice_ratio,
                'zero_crossing_rate': zcr,
                'dominant_frequency': dominant_freq,
                'quality_score': self.calculate_voice_score(rms, voice_ratio, dynamic_range, zcr)
            }
            
        except Exception as e:
            return {'filename': audio_file.name, 'error': str(e)}
    
    def calculate_voice_score(self, rms, voice_ratio, dynamic_range, zcr):
        """Calculate voice quality score using multiple parameters"""
        
        score = 0
        
        # RMS energy component (0-2 points)
        if rms > 0.5:
            score += 2
        elif rms > 0.1:
            score += 1.5
        elif rms > 0.05:
            score += 1
        
        # Voice band ratio (0-2 points)
        if voice_ratio > 0.6:
            score += 2
        elif voice_ratio > 0.4:
            score += 1.5
        elif voice_ratio > 0.2:
            score += 1
        
        # Dynamic range (0-1 point)
        if dynamic_range > 1.0:
            score += 1
        elif dynamic_range > 0.5:
            score += 0.5
        
        # Zero crossing rate (voice typically 0.05-0.15)
        if 0.05 <= zcr <= 0.15:
            score += 1
        elif 0.03 <= zcr <= 0.20:
            score += 0.5
        
        return min(score / 6, 1.0)  # Normalize to 0-1
    
    def create_visualization(self, analysis_data):
        """Create comprehensive visualization of the analysis results"""
        
        # Filter out error entries
        valid_data = [d for d in analysis_data if 'error' not in d]
        
        if not valid_data:
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('RF Digital Forensics Analysis - Top Voice Samples', fontsize=16, fontweight='bold')
        
        # Quality scores
        scores = [d['quality_score'] for d in valid_data]
        filenames = [d['filename'][:30] + '...' if len(d['filename']) > 30 else d['filename'] 
                    for d in valid_data]
        
        bars1 = ax1.barh(range(len(scores)), scores, color='steelblue')
        ax1.set_yticks(range(len(scores)))
        ax1.set_yticklabels(filenames, fontsize=8)
        ax1.set_xlabel('Voice Quality Score')
        ax1.set_title('Voice Quality Scores (Top Samples)')
        ax1.set_xlim(0, 1)
        
        # RMS vs Voice Ratio scatter
        rms_values = [d['rms_energy'] for d in valid_data]
        voice_ratios = [d['voice_band_ratio'] for d in valid_data]
        
        scatter = ax2.scatter(rms_values, voice_ratios, c=scores, cmap='viridis', s=100, alpha=0.7)
        ax2.set_xlabel('RMS Energy')
        ax2.set_ylabel('Voice Band Ratio (300-3400 Hz)')
        ax2.set_title('Energy vs Voice Content')
        plt.colorbar(scatter, ax=ax2, label='Quality Score')
        
        # Communication type breakdown
        comm_types = {}
        for d in valid_data:
            if 'CH22A_(Coast_Guard)' in d['filename']:
                comm_types['Coast Guard'] = comm_types.get('Coast Guard', 0) + 1
            elif 'CH13_(Bridge-to-Bridge)' in d['filename']:
                comm_types['Bridge-to-Bridge'] = comm_types.get('Bridge-to-Bridge', 0) + 1
            elif 'Approach_Control' in d['filename']:
                comm_types['Aviation ATC'] = comm_types.get('Aviation ATC', 0) + 1
            elif 'Tower_Control' in d['filename']:
                comm_types['Tower Control'] = comm_types.get('Tower Control', 0) + 1
            elif 'CH68_(Marina)' in d['filename']:
                comm_types['Marina'] = comm_types.get('Marina', 0) + 1
            else:
                comm_types['Other'] = comm_types.get('Other', 0) + 1
        
        if comm_types:
            labels, sizes = zip(*comm_types.items())
            ax3.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax3.set_title('Communication Types in Sample')
        
        # Duration distribution
        durations = [d['duration'] for d in valid_data]
        ax4.hist(durations, bins=10, color='lightcoral', edgecolor='black', alpha=0.7)
        ax4.set_xlabel('Duration (seconds)')
        ax4.set_ylabel('Number of Samples')
        ax4.set_title('Sample Duration Distribution')
        
        plt.tight_layout()
        
        # Save visualization
        viz_file = self.output_dir / f"rf_forensics_analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(viz_file, dpi=300, bbox_inches='tight')
        print(f"📊 Analysis visualization saved: {viz_file}")
        
        return viz_file
    
    def run_demo(self, num_samples=10):
        """Run complete RF forensics demo"""
        
        print("🎯 RF Digital Forensics Toolkit - Complete Pipeline Demo")
        print("=" * 60)
        
        # Load top samples from batch 1
        batch_file = "elevenlabs_batch_01.txt"
        if not Path(batch_file).exists():
            print("❌ Batch file not found. Run elevenlabs_batch_organizer.py first.")
            return
        
        with open(batch_file, 'r') as f:
            lines = [line.strip() for line in f.readlines() 
                    if not line.startswith('#') and line.strip()]
        
        print(f"📦 Analyzing top {num_samples} voice samples from Batch 1...")
        
        analysis_results = []
        
        for i, filename in enumerate(lines[:num_samples]):
            print(f"\n🔍 [{i+1}/{num_samples}] Analyzing: {filename}")
            
            audio_file = self.capture_dir / filename
            
            if not audio_file.exists():
                print(f"   ⚠️  File not found: {filename}")
                continue
            
            analysis = self.analyze_sample(audio_file)
            analysis_results.append(analysis)
            
            if 'error' not in analysis:
                print(f"   📊 Quality Score: {analysis['quality_score']:.3f}")
                print(f"   📊 Duration: {analysis['duration']:.1f}s")
                print(f"   📊 RMS Energy: {analysis['rms_energy']:.3f}")
                print(f"   📊 Voice Content: {analysis['voice_band_ratio']:.3f}")
            else:
                print(f"   ❌ Analysis error: {analysis['error']}")
        
        # Create comprehensive report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_samples_analyzed': len(analysis_results),
            'successful_analyses': len([r for r in analysis_results if 'error' not in r]),
            'average_quality_score': np.mean([r['quality_score'] for r in analysis_results if 'error' not in r]),
            'samples': analysis_results
        }
        
        # Save detailed report
        report_file = self.output_dir / f"forensics_analysis_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📋 Detailed analysis report saved: {report_file}")
        
        # Create visualization
        viz_file = self.create_visualization(analysis_results)
        
        # Summary
        valid_results = [r for r in analysis_results if 'error' not in r]
        if valid_results:
            avg_score = np.mean([r['quality_score'] for r in valid_results])
            avg_duration = np.mean([r['duration'] for r in valid_results])
            avg_voice_content = np.mean([r['voice_band_ratio'] for r in valid_results])
            
            print(f"\n🎉 Analysis Complete!")
            print(f"📊 Average Quality Score: {avg_score:.3f}")
            print(f"📊 Average Duration: {avg_duration:.1f}s")
            print(f"📊 Average Voice Content: {avg_voice_content:.3f}")
            print(f"📁 Results saved to: {self.output_dir}")
        
        return report_file, viz_file

def main():
    demo = RFForensicsDemo()
    demo.run_demo(15)  # Analyze top 15 samples

if __name__ == "__main__":
    main()
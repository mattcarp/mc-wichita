#!/usr/bin/env python3
"""
ElevenLabs Batch Organizer
Organizes filtered voice files into processing batches and estimates costs
"""

import pandas as pd
from pathlib import Path
import soundfile as sf
import numpy as np
from datetime import datetime, timezone

class ElevenLabsBatchOrganizer:
    """Organize voice files for optimal ElevenLabs processing"""
    
    def __init__(self, filtered_file="voice_filtered_list.txt", capture_dir="rf_captures/autonomous_hunt_20250911_212457"):
        self.filtered_file = filtered_file
        self.capture_dir = Path(capture_dir)
        
        # ElevenLabs pricing (estimated)
        self.cost_per_minute = 0.30  # $0.30 per minute estimate
        
    def analyze_filtered_files(self):
        """Analyze the filtered voice files"""
        
        print("📊 Analyzing filtered voice files...")
        
        # Read filtered list
        with open(self.filtered_file, 'r') as f:
            lines = [line.strip() for line in f.readlines() if not line.startswith('#') and line.strip()]
        
        files_data = []
        total_duration = 0
        
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 3:
                filename = parts[0]
                score = float(parts[1])
                rms = float(parts[2])
                
                # Get file duration
                try:
                    audio_path = self.capture_dir / filename
                    if audio_path.exists():
                        audio, sample_rate = sf.read(str(audio_path))
                        duration = len(audio) / sample_rate
                        total_duration += duration
                    else:
                        duration = 0
                except:
                    duration = 0
                
                # Categorize by frequency type
                freq_type = self.categorize_frequency(filename)
                
                files_data.append({
                    'filename': filename,
                    'score': score,
                    'rms': rms,
                    'duration': duration,
                    'freq_type': freq_type
                })
        
        df = pd.DataFrame(files_data)
        
        # Quality tiers
        excellent = df[df['score'] > 0.6]
        good = df[(df['score'] > 0.4) & (df['score'] <= 0.6)]
        fair = df[(df['score'] > 0.25) & (df['score'] <= 0.4)]
        
        print(f"\n📈 QUALITY ANALYSIS:")
        print(f"   Total Filtered Files: {len(df):,}")
        print(f"   Total Duration: {total_duration/60:.1f} minutes")
        print(f"   EXCELLENT (>0.60): {len(excellent):,} files ({len(excellent)/len(df)*100:.1f}%)")
        print(f"   GOOD (0.40-0.60): {len(good):,} files ({len(good)/len(df)*100:.1f}%)")
        print(f"   FAIR (0.25-0.40): {len(fair):,} files ({len(fair)/len(df)*100:.1f}%)")
        
        # Cost estimates
        cost_all = total_duration / 60 * self.cost_per_minute
        cost_excellent = excellent['duration'].sum() / 60 * self.cost_per_minute
        cost_good_plus = (excellent['duration'].sum() + good['duration'].sum()) / 60 * self.cost_per_minute
        
        print(f"\n💰 COST ESTIMATES:")
        print(f"   All Filtered Files: ${cost_all:.2f}")
        print(f"   Excellent Only: ${cost_excellent:.2f}")
        print(f"   Excellent + Good: ${cost_good_plus:.2f}")
        
        # Original cost comparison
        original_cost = 18216 * 6 / 60 * self.cost_per_minute  # Assuming 6 sec average
        print(f"   Original (all 18,216): ${original_cost:.2f}")
        print(f"   Savings: ${original_cost - cost_all:.2f} ({(original_cost - cost_all)/original_cost*100:.1f}%)")
        
        return df, excellent, good, fair
    
    def categorize_frequency(self, filename):
        """Categorize by frequency type"""
        
        if any(x in filename for x in ['CH16', 'Emergency']):
            return 'Maritime Emergency'
        elif any(x in filename for x in ['Coast_Guard', 'CH22A']):
            return 'Coast Guard'
        elif any(x in filename for x in ['Bridge-to-Bridge', 'CH13']):
            return 'Maritime Navigation'
        elif any(x in filename for x in ['Tower', 'Approach', 'Flight']):
            return 'Aviation ATC'
        elif any(x in filename for x in ['Air-to-Air']):
            return 'Aviation Pilot'
        elif any(x in filename for x in ['CH', 'Marina', 'Port']):
            return 'Maritime Commercial'
        else:
            return 'Other'
    
    def create_processing_batches(self, df, batch_size=100):
        """Create processing batches for ElevenLabs"""
        
        print(f"\n📦 Creating processing batches (size: {batch_size})...")
        
        # Sort by score (highest quality first)
        df_sorted = df.sort_values('score', ascending=False)
        
        batches = []
        for i in range(0, len(df_sorted), batch_size):
            batch = df_sorted.iloc[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            batch_info = {
                'batch_number': batch_num,
                'files': batch['filename'].tolist(),
                'avg_score': batch['score'].mean(),
                'total_duration': batch['duration'].sum(),
                'estimated_cost': batch['duration'].sum() / 60 * self.cost_per_minute,
                'freq_types': batch['freq_type'].value_counts().to_dict()
            }
            
            batches.append(batch_info)
        
        print(f"   Created {len(batches)} batches")
        
        return batches
    
    def generate_processing_report(self, df, excellent, good, fair, batches):
        """Generate comprehensive processing report"""
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_file = f"elevenlabs_processing_plan_{timestamp}.txt"
        
        report = f"""
🎙️ ELEVENLABS PROCESSING PLAN
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
=====================================

📊 SUMMARY:
• Original Files: 18,216
• After Voice Filtering: {len(df):,} files ({len(df)/18216*100:.1f}%)
• Cost Reduction: {(18216-len(df))/18216*100:.1f}%

🏆 QUALITY TIERS:
• EXCELLENT (>0.60): {len(excellent):,} files - PROCESS FIRST
• GOOD (0.40-0.60): {len(good):,} files - High priority  
• FAIR (0.25-0.40): {len(fair):,} files - Consider for batch processing

📈 BY COMMUNICATION TYPE:
"""
        
        # Frequency type breakdown
        freq_counts = df['freq_type'].value_counts()
        for freq_type, count in freq_counts.items():
            avg_score = df[df['freq_type'] == freq_type]['score'].mean()
            report += f"• {freq_type}: {count:,} files (avg score: {avg_score:.3f})\n"
        
        report += f"""

💰 COST ANALYSIS:
• All Filtered Files: ${df['duration'].sum()/60 * self.cost_per_minute:.2f}
• Excellent Only: ${excellent['duration'].sum()/60 * self.cost_per_minute:.2f}
• Excellent + Good: ${(excellent['duration'].sum() + good['duration'].sum())/60 * self.cost_per_minute:.2f}

🎯 RECOMMENDED STRATEGY:
1. Start with EXCELLENT tier ({len(excellent):,} files, ~${excellent['duration'].sum()/60 * self.cost_per_minute:.2f})
2. If results are good, process GOOD tier ({len(good):,} files, ~${good['duration'].sum()/60 * self.cost_per_minute:.2f})
3. FAIR tier can be processed later if needed ({len(fair):,} files, ~${fair['duration'].sum()/60 * self.cost_per_minute:.2f})

📦 PROCESSING BATCHES:
"""
        
        # Top 5 batches
        for i, batch in enumerate(batches[:5]):
            report += f"""
Batch {batch['batch_number']}:
• Files: {len(batch['files'])}
• Avg Score: {batch['avg_score']:.3f}
• Duration: {batch['total_duration']:.1f}s
• Est Cost: ${batch['estimated_cost']:.2f}
• Types: {', '.join([f"{k}({v})" for k, v in batch['freq_types'].items()])}
"""
        
        report += f"""

🚀 NEXT STEPS:
1. Review top files manually (listen to samples)
2. Start with Batch 1-3 for initial testing
3. Adjust strategy based on ElevenLabs results
4. Scale up processing based on quality outcomes

📁 Files are ready in: {self.capture_dir}/
📝 Filtered list: {self.filtered_file}
"""
        
        # Save report
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(report)
        print(f"📄 Full report saved to: {report_file}")
        
        return report_file
    
    def save_batch_files(self, batches, num_batches=5):
        """Save individual batch file lists"""
        
        print(f"\n💾 Saving batch files for top {num_batches} batches...")
        
        for i, batch in enumerate(batches[:num_batches]):
            batch_file = f"elevenlabs_batch_{batch['batch_number']:02d}.txt"
            
            with open(batch_file, 'w') as f:
                f.write(f"# ElevenLabs Processing Batch {batch['batch_number']}\n")
                f.write(f"# Generated: {datetime.now(timezone.utc)}\n")
                f.write(f"# Files: {len(batch['files'])}\n")
                f.write(f"# Avg Score: {batch['avg_score']:.3f}\n")
                f.write(f"# Est Cost: ${batch['estimated_cost']:.2f}\n\n")
                
                for filename in batch['files']:
                    f.write(f"{filename}\n")
            
            print(f"   ✅ {batch_file} - {len(batch['files'])} files, ${batch['estimated_cost']:.2f}")

def main():
    """Generate ElevenLabs processing plan"""
    
    print("🎯 ElevenLabs Batch Organizer")
    print("=" * 50)
    
    organizer = ElevenLabsBatchOrganizer()
    
    # Analyze filtered files
    df, excellent, good, fair = organizer.analyze_filtered_files()
    
    # Create processing batches
    batches = organizer.create_processing_batches(df, batch_size=50)  # Smaller batches for testing
    
    # Generate report
    report_file = organizer.generate_processing_report(df, excellent, good, fair, batches)
    
    # Save batch files
    organizer.save_batch_files(batches, num_batches=10)
    
    print(f"\n✅ Processing plan complete!")
    print(f"🎯 Recommendation: Start with elevenlabs_batch_01.txt ({batches[0]['avg_score']:.3f} avg score)")
    
    return df, batches

if __name__ == "__main__":
    df, batches = main()
#!/usr/bin/env python3
"""
ElevenLabs Voice Isolator - Production-ready RF audio processing
Integrates with ElevenLabs Voice Isolation API for forensic-quality audio cleanup
"""

import os
import requests
import soundfile as sf
import numpy as np
from pathlib import Path
import json
import time
from datetime import datetime, timezone

class VoiceIsolator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            print("⚠️  ElevenLabs API key not found in environment")
            print("   Set ELEVENLABS_API_KEY or pass as parameter")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self.capture_dir = Path("rf_captures/autonomous_hunt_20250911_212457")
        self.output_dir = Path("elevenlabs_isolated")
        self.output_dir.mkdir(exist_ok=True)
        
        # Cost tracking
        self.cost_per_second = 0.016  # $0.016 per second
        self.total_cost = 0
        self.processed_files = []
        
    def isolate_voice(self, audio_file, save_original_analysis=True):
        """Isolate voice from RF audio using ElevenLabs API"""
        
        if not self.api_key:
            print(f"❌ Cannot process {audio_file.name} - No API key")
            return None
        
        print(f"🎵 Processing: {audio_file.name}")
        
        try:
            # Read and analyze original audio
            audio_data, sample_rate = sf.read(str(audio_file))
            duration = len(audio_data) / sample_rate
            
            # Calculate cost
            file_cost = duration * self.cost_per_second
            self.total_cost += file_cost
            
            print(f"   📊 Duration: {duration:.1f}s | Cost: ${file_cost:.3f}")
            
            # Prepare audio for API (16-bit PCM WAV)
            audio_16bit = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            
            import io
            buffer = io.BytesIO()
            sf.write(buffer, audio_16bit, sample_rate, format='WAV')
            buffer.seek(0)
            audio_bytes = buffer.read()
            
            # API request
            url = f"{self.base_url}/audio-isolation"
            headers = {"xi-api-key": self.api_key}
            files = {"audio": ("audio.wav", audio_bytes, "audio/wav")}
            
            print(f"   🚀 Sending to ElevenLabs...")
            response = requests.post(url, headers=headers, files=files, timeout=120)
            
            if response.status_code == 200:
                # Save isolated audio
                output_file = self.output_dir / f"isolated_{audio_file.name}"
                with open(output_file, 'wb') as f:
                    f.write(response.content)
                
                # Verify output
                try:
                    isolated_audio, _ = sf.read(str(output_file))
                    isolated_duration = len(isolated_audio) / sample_rate
                    
                    result = {
                        'original_file': str(audio_file),
                        'isolated_file': str(output_file),
                        'duration': duration,
                        'sample_rate': sample_rate,
                        'cost': file_cost,
                        'success': True,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    
                    self.processed_files.append(result)
                    
                    print(f"   ✅ Success → {output_file.name}")
                    return result
                
                except Exception as e:
                    print(f"   ⚠️  Output verification failed: {e}")
                    return None
            else:
                print(f"   ❌ API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"   ❌ Processing error: {e}")
            return None
    
    def process_batch(self, batch_file, max_files=None, max_cost=None):
        """Process a batch of files with cost controls"""
        
        print("🎯 ElevenLabs Voice Isolation - Batch Processing")
        print("=" * 60)
        
        if not Path(batch_file).exists():
            print(f"❌ Batch file not found: {batch_file}")
            return
        
        # Load batch
        with open(batch_file, 'r') as f:
            lines = [line.strip() for line in f.readlines() 
                    if not line.startswith('#') and line.strip()]
        
        if max_files:
            lines = lines[:max_files]
        
        print(f"📦 Processing {len(lines)} files from {batch_file}")
        
        if max_cost:
            print(f"💰 Cost limit: ${max_cost:.2f}")
        
        processed_count = 0
        
        for i, filename in enumerate(lines):
            print(f"\n[{i+1}/{len(lines)}]", end=" ")
            
            # Check cost limit
            if max_cost and self.total_cost >= max_cost:
                print(f"💰 Cost limit reached (${max_cost:.2f})")
                break
            
            audio_file = self.capture_dir / filename
            
            if not audio_file.exists():
                print(f"⚠️  File not found: {filename}")
                continue
            
            result = self.isolate_voice(audio_file)
            if result:
                processed_count += 1
            
            # Rate limiting
            time.sleep(1)
        
        # Save processing report
        report = {
            'batch_file': batch_file,
            'total_files': len(lines),
            'processed_files': processed_count,
            'total_cost': self.total_cost,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'files': self.processed_files
        }
        
        report_file = self.output_dir / f"processing_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n🎉 Batch processing complete!")
        print(f"📊 Processed: {processed_count}/{len(lines)} files")
        print(f"💰 Total cost: ${self.total_cost:.2f}")
        print(f"📁 Isolated files: {self.output_dir}")
        print(f"📋 Report: {report_file}")
        
        return report
    
    def demo_mode(self):
        """Demo mode - shows what would be processed without API calls"""
        
        print("🎯 ElevenLabs Voice Isolation - Demo Mode")
        print("   (No actual API calls - cost estimation only)")
        print("=" * 60)
        
        batch_file = "elevenlabs_batch_01.txt"
        
        if not Path(batch_file).exists():
            print(f"❌ Batch file not found: {batch_file}")
            return
        
        with open(batch_file, 'r') as f:
            lines = [line.strip() for line in f.readlines() 
                    if not line.startswith('#') and line.strip()]
        
        print(f"📦 Analyzing first 5 files from {batch_file}...")
        
        total_cost = 0
        total_duration = 0
        
        for i, filename in enumerate(lines[:5]):
            print(f"\n🔍 [{i+1}/5] {filename}")
            
            audio_file = self.capture_dir / filename
            
            if not audio_file.exists():
                print(f"   ⚠️  File not found")
                continue
            
            try:
                audio_data, sample_rate = sf.read(str(audio_file))
                duration = len(audio_data) / sample_rate
                cost = duration * self.cost_per_second
                
                total_duration += duration
                total_cost += cost
                
                print(f"   📊 Duration: {duration:.1f}s")
                print(f"   💰 Cost: ${cost:.3f}")
                print(f"   🎯 Would isolate voice and save as: isolated_{filename}")
                
            except Exception as e:
                print(f"   ❌ Analysis error: {e}")
        
        print(f"\n📊 Demo Summary:")
        print(f"   Total Duration: {total_duration:.1f}s")
        print(f"   Total Cost: ${total_cost:.2f}")
        print(f"   Average: ${total_cost/5:.3f} per file")

def main():
    isolator = VoiceIsolator()
    
    # Run in demo mode first
    isolator.demo_mode()
    
    print(f"\n{'='*60}")
    print("To process files with ElevenLabs API:")
    print("1. Set ELEVENLABS_API_KEY environment variable")
    print("2. Run: isolator.process_batch('elevenlabs_batch_01.txt', max_files=3, max_cost=2.50)")

if __name__ == "__main__":
    main()
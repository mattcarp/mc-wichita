#!/usr/bin/env python3
"""
Maritime & Aviation API Endpoints
FastAPI endpoints for RF capture and processing
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import subprocess
import json
from pathlib import Path
from datetime import datetime, timezone
from maritime_aviation_capture import MaritimeAviationCapture

# API Models
class CaptureRequest(BaseModel):
    frequency: float
    band: str  # 'maritime' or 'aviation'
    duration: Optional[int] = 10
    process_with_ai: Optional[bool] = True

class BatchCaptureRequest(BaseModel):
    band: str  # 'maritime', 'aviation', or 'all'
    channels: Optional[List[float]] = None
    process_with_ai: Optional[bool] = True

class CaptureStatus(BaseModel):
    status: str
    frequency: float
    description: str
    raw_audio: Optional[str]
    cleaned_audio: Optional[str]
    timestamp: str

# Initialize capture system
capture_system = MaritimeAviationCapture()

def add_maritime_aviation_routes(app: FastAPI):
    """Add maritime and aviation routes to existing API"""
    
    @app.get("/api/maritime/channels")
    async def get_maritime_channels():
        """Get list of maritime VHF channels"""
        return {
            "band": "Maritime VHF",
            "frequency_range": "156-162 MHz",
            "channels": [
                {"frequency": freq, "description": desc}
                for freq, desc in capture_system.maritime_channels.items()
            ]
        }
    
    @app.get("/api/aviation/channels")
    async def get_aviation_channels():
        """Get list of aviation band channels"""
        return {
            "band": "Aviation",
            "frequency_range": "118-137 MHz", 
            "channels": [
                {"frequency": freq, "description": desc}
                for freq, desc in capture_system.aviation_channels.items()
            ]
        }
    
    @app.post("/api/capture/single", response_model=CaptureStatus)
    async def capture_single_frequency(request: CaptureRequest):
        """Capture a single frequency"""
        try:
            # Check HackRF connection
            result = subprocess.run(['hackrf_info'], capture_output=True, text=True)
            if 'No HackRF boards found' in result.stderr:
                raise HTTPException(status_code=503, detail="HackRF not connected")
            
            # Capture IQ data
            desc = capture_system.maritime_channels.get(request.frequency) or \
                   capture_system.aviation_channels.get(request.frequency) or \
                   f"{request.band}_{request.frequency}MHz"
            
            iq_file = capture_system.capture_iq_data(request.frequency, desc)
            if not iq_file:
                raise HTTPException(status_code=500, detail="Capture failed")
            
            # Demodulate based on band
            wav_file = str(capture_system.output_dir / f"{request.band}_{request.frequency}MHz.wav")
            if request.band == 'maritime':
                capture_system.demodulate_fm(iq_file, wav_file)
            else:
                capture_system.demodulate_am(iq_file, wav_file)
            
            # Process with AI if requested
            cleaned_file = None
            if request.process_with_ai and request.duration > 4.6:
                cleaned_file = capture_system.process_with_elevenlabs(wav_file)
            
            return CaptureStatus(
                status="success",
                frequency=request.frequency,
                description=desc,
                raw_audio=wav_file,
                cleaned_audio=cleaned_file,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/capture/batch")
    async def batch_capture(request: BatchCaptureRequest, background_tasks: BackgroundTasks):
        """Start batch capture of multiple frequencies"""
        try:
            # Check HackRF
            result = subprocess.run(['hackrf_info'], capture_output=True, text=True)
            if 'No HackRF boards found' in result.stderr:
                raise HTTPException(status_code=503, detail="HackRF not connected")
            
            # Start background capture
            task_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            
            def run_batch_capture():
                results = []
                
                if request.band in ['maritime', 'all']:
                    results.extend(capture_system.scan_maritime_channels())
                
                if request.band in ['aviation', 'all']:
                    results.extend(capture_system.scan_aviation_channels())
                
                # Save results
                capture_system.generate_demo_data(
                    [r for r in results if r['band'] == 'maritime'],
                    [r for r in results if r['band'] == 'aviation']
                )
            
            background_tasks.add_task(run_batch_capture)
            
            return {
                "status": "started",
                "task_id": task_id,
                "message": f"Batch capture started for {request.band} band"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/capture/results")
    async def get_capture_results():
        """Get latest capture results"""
        results_file = capture_system.output_dir / 'capture_results.json'
        
        if not results_file.exists():
            raise HTTPException(status_code=404, detail="No capture results found")
        
        with open(results_file, 'r') as f:
            return json.load(f)
    
    @app.get("/api/audio/{filename}")
    async def get_audio_file(filename: str):
        """Serve audio files"""
        file_path = capture_system.output_dir / filename
        
        if not file_path.exists():
            # Check audio_samples directory
            alt_path = Path("audio_samples") / filename
            if alt_path.exists():
                file_path = alt_path
            else:
                raise HTTPException(status_code=404, detail="Audio file not found")
        
        return FileResponse(file_path)
    
    @app.get("/api/spectrum/analyze")
    async def analyze_spectrum(frequency: float, band: str):
        """Analyze spectrum for a specific frequency"""
        try:
            # Quick spectrum scan using HackRF
            freq_hz = int(frequency * 1e6)
            cmd = f"timeout 0.5 hackrf_transfer -r - -f {freq_hz} -s 2000000 -n 1000000 -l 32 -g 20 -a 1 2>&1"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Parse power level
            power = -100
            if "average power" in result.stderr:
                try:
                    power_line = [l for l in result.stderr.split('\n') if "average power" in l][0]
                    power = float(power_line.split("average power")[1].split("dBfs")[0].strip())
                except:
                    pass
            
            # Determine signal strength
            if power > -5:
                signal_strength = "VERY STRONG"
                status = "active"
            elif power > -20:
                signal_strength = "Strong"
                status = "active"
            elif power > -40:
                signal_strength = "Good"
                status = "active"
            elif power > -60:
                signal_strength = "Weak"
                status = "weak"
            else:
                signal_strength = "No signal"
                status = "inactive"
            
            return {
                "frequency": frequency,
                "band": band,
                "power_dbfs": power,
                "signal_strength": signal_strength,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return app

# For testing standalone
if __name__ == "__main__":
    import uvicorn
    app = FastAPI(title="Maritime & Aviation RF API")
    app = add_maritime_aviation_routes(app)
    uvicorn.run(app, host="0.0.0.0", port=8001)
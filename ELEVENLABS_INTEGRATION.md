# ElevenLabs Voice Isolation Integration

## Setup

Export your ElevenLabs API key:
```bash
export ELEVENLABS_API_KEY='your_key_here'
```

## Usage

### Basic Client (src/elevenlabs_client.py)
```python
from src.elevenlabs_client import ElevenLabsClient
from pathlib import Path

client = ElevenLabsClient()
clean_audio = client.isolate_file(Path("noisy_audio.wav"))
print(f"Clean audio saved to: {clean_audio}")
```

### RF Processor (src/elevenlabs_rf_processor.py)
```python
from src.elevenlabs_rf_processor import ElevenLabsRFProcessor
from pathlib import Path

processor = ElevenLabsRFProcessor()
result = processor.process_audio(Path("rf_capture.wav"))
```

## Testing

Once SDRplay is reconnected, create RF audio samples:
1. Connect SDRplay hardware
2. Capture audio from various frequencies (VHF marine, aviation emergency, etc.)
3. Test voice isolation pipeline with real RF noise scenarios

### Audio Preprocessing Module (src/audio_preprocessor.py)
```python
from src.audio_preprocessor import AudioPreprocessor
from pathlib import Path

preprocessor = AudioPreprocessor()
clean_audio = preprocessor.process_file(Path("noisy_rf.wav"))
```

## Features

✅ **ElevenLabsClient** - Retry logic, timeout handling, error management  
✅ **Audio Preprocessing** - Format conversion, normalization, pre-filtering  
✅ **Buffering System** - Thread-safe streaming buffers for continuous processing  
✅ **RF Pipeline Integration** - Wichita pipeline → Preprocessor → ElevenLabs → Clean audio  
✅ **Streaming Support** - Real-time chunk processing for live RF streams  

## Current Status

✅ ElevenLabsClient implemented with retry logic and error handling  
✅ RF processor updated to use new client  
✅ Audio preprocessing module with format conversion, normalization, filtering  
✅ Buffering system for continuous streaming  
⏳ Waiting for SDRplay reconnection to create test samples  
⏳ Real RF audio validation pending hardware connection  
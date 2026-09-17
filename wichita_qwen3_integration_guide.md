
# Wichita + Qwen3-ASR API Integration Guide

## Step 1: API Setup
```python
import requests

# Alibaba Cloud API endpoint
API_BASE = "https://bailian.console.alibabacloud.com"
MODEL = "qwen3-asr-flash"

# Headers (API key needed)
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
```

## Step 2: Audio Upload & Processing
```python
def transcribe_maritime_audio(audio_file, context):
    # Convert audio to base64
    with open(audio_file, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    
    payload = {
        "model": "qwen3-asr-flash",
        "audio": audio_b64,
        "context": context,
        "language": "auto",
        "enable_itn": True,
        "enable_punctuation": True
    }
    
    response = requests.post(f"{API_BASE}/api/v1/asr", 
                           headers=headers, json=payload)
    return response.json()
```

## Step 3: Maritime Context Enhancement
- Use maritime terminology for better recognition
- Include emergency keywords
- Add geographic context (Malta, Mediterranean)
- Specify frequency/channel information

## Step 4: Integration with Wichita
- Real-time processing of SDRplay captures
- Automatic threat detection
- Emergency alert system
- Multi-language support (Maltese, Arabic, Italian)

## Cost Optimization
- 10-hour free trial quota
- $0.11 USD per hour after trial
- Perfect for continuous monitoring

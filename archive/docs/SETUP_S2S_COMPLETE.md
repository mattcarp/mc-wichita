# 📚 KENNETH S2S SETUP DOCUMENTATION

## ✅ COMPLETED SETUP STEPS

### 1. Environment Configuration
- Created `.env.local` file with OpenAI API key placeholder
- Initialized npm project (`package.json` created)
- Created Python virtual environment (`venv/`)

### 2. Installed Dependencies

#### Node.js Packages:
```bash
✅ openai (v5.19.1) - Main OpenAI SDK
✅ realtime-api-beta (v0.5.0) - Realtime API support
```

#### Python Packages (in venv):
```bash
✅ openai - OpenAI Python SDK
✅ pyaudio - Audio capture/playback
✅ websocket-client - WebSocket support
✅ python-dotenv - Environment variable management
✅ numpy - Numerical processing
✅ scipy - Signal processing
```

#### System Dependencies:
```bash
✅ portaudio (v19.7.0) - Audio library for PyAudio
```

---

## 🚀 HOW TO USE

### 1. Add Your OpenAI API Key
Edit `.env.local` and replace `your-api-key-here` with your actual key:
```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
```

### 2. Activate Python Environment
```bash
cd /Users/mattcarp/Documents/projects/rf-forensics-toolkit
source venv/bin/activate
```

### 3. Run the S2S Test
```bash
python3 kenneth_s2s_quickstart.py
```

### 4. Connect to SDR++
The system will automatically capture audio from your default input.
To route SDR++ audio:
1. Use a virtual audio cable (BlackHole, Soundflower)
2. Set SDR++ audio output to the virtual cable
3. Set Python script input to the virtual cable

---

## 📁 PROJECT STRUCTURE

```
rf-forensics-toolkit/
├── .env.local                    # API keys and configuration
├── package.json                  # Node.js dependencies
├── node_modules/                 # Node packages
├── venv/                         # Python virtual environment
├── kenneth_s2s_quickstart.py     # Basic S2S test script
├── kenneth_s2s_integration.md    # S2S integration plan
├── ARCHITECTURE.md               # Complete system architecture
├── KENNETH_PRD.md               # Product requirements document
├── TASKMASTER_S2S_TODO.md       # S2S implementation tasks
└── SDR++.app/                   # SDR++ application
```

---

## 🔧 TECHNICAL DETAILS

### Audio Pipeline:
```
SDR++ (RF → Audio) → Virtual Cable → Python (pyaudio) → S2S API → Emotional Analysis
```

### S2S Configuration:
- Model: gpt-4-realtime
- Temperature: 0.9
- Voice Detection: semantic
- Sample Rate: 16kHz
- Buffer: 30 seconds

### Alert Thresholds:
- Stress Critical: 80%
- Panic Emergency: 90%
- Exhaustion Warning: 70%

---

## 🎯 NEXT STEPS

### Immediate (Today):
1. [ ] Test with real OpenAI API key
2. [ ] Capture live audio from SDR++
3. [ ] Log first emotional analysis

### This Week:
1. [ ] Build TypeScript S2S client
2. [ ] Create WebSocket server for dashboard
3. [ ] Implement multi-agent system

### Next Week:
1. [ ] Enhanced dashboard with emotion meters
2. [ ] Geographic plotting on Malta map
3. [ ] Alert system integration

---

## 🐛 TROUBLESHOOTING

### If "No module named 'openai'":
```bash
source venv/bin/activate
pip install openai
```

### If PyAudio fails:
```bash
brew install portaudio
pip install --upgrade pyaudio
```

### If API key not found:
1. Check `.env.local` has correct key
2. Ensure no spaces around `=` sign
3. Try exporting directly: `export OPENAI_API_KEY=sk-xxxx`

### If no audio input:
1. Check system permissions for microphone
2. Verify SDR++ is outputting audio
3. Test with: `python3 -c "import pyaudio; print(pyaudio.PyAudio().get_device_count())"`

---

## 📊 TESTING CHECKLIST

- [ ] Python environment activated
- [ ] All packages installed successfully
- [ ] API key configured
- [ ] Test script runs without errors
- [ ] Audio capture working
- [ ] Mock emotional analysis displays
- [ ] Alert triggers on high stress

---

## 🔐 SECURITY NOTES

1. **Never commit `.env.local` to git** (already in .gitignore)
2. **API keys should stay local** - use environment variables
3. **Audio data is sensitive** - handle with care
4. **Implement rate limiting** to avoid excessive API calls

---

## 📞 SUPPORT

If issues persist after following this guide:
1. Check the error logs in `websocket_server.log`
2. Review `ARCHITECTURE.md` for system design
3. See `TASKMASTER_S2S_TODO.md` for implementation status
4. Start new conversation with this context

---

*Last Updated: September 2025*
*Kenneth v2.0 - RF Forensics with Emotional Intelligence*

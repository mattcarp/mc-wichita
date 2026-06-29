# Tomorrow's Real RF Voice Capture Mission

## Setup: SDRplay + Roof Antenna

### Hardware Connection
1. **SDRplay RSPdx** via USB (already confirmed working)
2. **Roof antenna** - optimize for VHF (118-170 MHz)
3. **Antenna position** - highest practical point, clear horizon

### Software Ready
- ✅ **SDRplay drivers installed** (`/usr/local/lib/libsdrplay_api.dylib`)
- ✅ **Voice hunting scanner** (`voice_hunting_scanner.py`)
- ✅ **ElevenLabs pipeline** (`elevenlabs_rf_processor.py`)
- ✅ **Audio analysis tools** (`audio_comparison_suite.py`)

## Prime Voice Capture Targets

### 🚢 Maritime VHF (Best: 0800-1800 Local)

| Channel | Frequency | Purpose | Activity Level |
|---------|-----------|---------|----------------|
| **CH16** | 156.800 MHz | Emergency/Calling | **HIGH** - Monitored 24/7 |
| CH13 | 156.650 MHz | Bridge-to-Bridge | **HIGH** - Ship navigation |
| CH09 | 156.450 MHz | General Calling | **MEDIUM** - Commercial |
| CH06 | 156.300 MHz | Ship Safety | **MEDIUM** - Safety comms |
| CH22A | 157.100 MHz | Coast Guard | **HIGH** - Official traffic |

**Expected Voice Types:**
- Coast Guard emergency responses
- Ship-to-ship navigation calls
- Harbor pilot communications
- Commercial vessel operations

### ✈️ Aviation VHF (Best: 0600-2200 Local)

| Purpose | Frequency Range | Activity Level |
|---------|-----------------|----------------|
| **Emergency** | 121.500 MHz | **HIGH** - Always monitored |
| Tower Control | 118.0-121.0 MHz | **HIGH** - Active airports |
| Approach/Departure | 119.0-121.0 MHz | **HIGH** - Terminal control |
| Ground Control | 121.6-121.9 MHz | **MEDIUM** - Airport ground |
| Air-to-Air | 122.750 MHz | **MEDIUM** - Pilot chat |

**Expected Voice Types:**
- Pilot-controller communications
- Emergency declarations
- Flight following
- Airport operations

## Capture Strategy

### Phase 1: Quick Scan (10 minutes)
```bash
python3 voice_hunting_scanner.py
```
- **5-second samples** on each frequency
- **Voice activity detection** 
- **Identify active frequencies**

### Phase 2: Targeted Capture (30+ minutes each)
- **Focus on frequencies with detected voice**
- **30-60 second samples** for complete conversations
- **Multiple captures** to get variety

### Phase 3: ElevenLabs Processing
```bash
export ELEVENLABS_API_KEY='your_key'
python3 elevenlabs_rf_processor.py [captured_files]
```
- **Before/after audio comparison**
- **Visual spectral analysis**
- **Objective quality metrics**

## Expected Results

### 🎧 Audio Examples We'll Capture:
1. **"Coast Guard Station, this is vessel [name]..."** - Emergency/assistance calls
2. **"Tower, Cessna [callsign], request landing..."** - Pilot-controller communications
3. **"Traffic, [airport name], Piper [callsign]..."** - Pilot position reports
4. **"Security Alert, all vessels..."** - Coast Guard broadcasts

### 📊 Processing Pipeline:
```
Real RF → SDRplay → Demodulation → ElevenLabs → Clean Voice
   ↓
Noisy maritime/aviation audio with static/interference
   ↓
Crystal clear voice isolation for forensic analysis
```

## Timing Recommendations

### Maritime (Water-dependent)
- **Morning**: 0800-1200 (commercial vessels departing)
- **Afternoon**: 1400-1800 (return traffic)
- **Weekend**: Recreational boat traffic

### Aviation (Airport-dependent)
- **Rush hours**: 0700-0900, 1700-1900 (business flights)
- **Midday**: 1000-1500 (training flights, general aviation)
- **Weekend**: 0900-1700 (recreational flying)

## Success Metrics
- ✅ **Real human speech captured** (not just carriers/noise)
- ✅ **Multiple frequency sources** (maritime + aviation)
- ✅ **Complete conversations** (not just fragments)
- ✅ **Successful ElevenLabs processing** (dramatic noise reduction)
- ✅ **Before/after audio comparison** (clear improvement demonstration)

## Fallback Plan
If no voice activity detected:
1. **Verify antenna connections**
2. **Try different times of day**
3. **Scan wider frequency ranges**
4. **Check for local repeater activity**
5. **Monitor emergency frequencies longer**

---

**Tomorrow = Real RF Voice Capture Mission! 🎯**
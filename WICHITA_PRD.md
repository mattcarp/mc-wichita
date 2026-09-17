# 📋 WICHITA PRODUCT REQUIREMENTS DOCUMENT (PRD)
## RF Forensics Platform with S2S Emotional Intelligence

**Version:** 2.0  
**Date:** September 2025  
**Status:** In Development  
**Location:** Malta (Mediterranean)

---

## 1. EXECUTIVE SUMMARY

Wichita is an emotionally-intelligent RF forensics platform that monitors maritime and aviation frequencies to:
1. **Detect threats** through voice stress and behavioral analysis
2. **Save lives** by identifying both explicit and implicit distress signals

The integration of OpenAI's Speech-to-Speech (S2S) technology transforms Wichita from a passive listening system into an active emotional intelligence platform capable of detecting panic, exhaustion, and fear that traditional transcription misses.

---

## 2. PROBLEM STATEMENT

### Current Limitations in RF Monitoring:
- **Traditional systems miss emotional context** - "I'm fine" said while crying
- **Transcription loses critical information** - breathing patterns, voice stress
- **Language barriers** - Malta's multilingual environment (Maltese/English/Italian/Arabic)
- **Delayed response** - Human operators can't monitor all frequencies 24/7
- **Implicit distress ignored** - No words doesn't mean no emergency

### Real-World Scenarios We Must Address:
1. **Fisherman taking on water** - Heavy breathing, no explicit distress call
2. **Pilot experiencing hypoxia** - Slurred speech, confusion
3. **Yacht in distress** - Crying children in background
4. **Criminal coordination** - Normal words with threatening tone
5. **Medical emergency** - Labored breathing, weakening voice

---

## 3. SOLUTION OVERVIEW

### Wichita S2S Architecture:
```
RF Signal → SDR++ → Audio → S2S Analysis → Emotional Intelligence → Alert
```

### Key Innovations:
- **Emotion Detection**: Stress, panic, exhaustion, confusion
- **Accent Preservation**: Maintains Maltese, Arabic, Italian nuances
- **Real-time Processing**: <500ms from capture to alert
- **Multi-agent System**: Specialized agents for different emergencies
- **No transcription loss**: Direct audio-to-understanding

---

## 4. USER PERSONAS

### Primary Users:

#### 1. Coast Guard Operator
- **Needs**: Immediate alerts for vessels in distress
- **Pain Points**: Can't monitor all channels simultaneously
- **Wichita Solution**: Automated monitoring with emotion-based prioritization

#### 2. Air Traffic Controller
- **Needs**: Detect pilot incapacitation or confusion
- **Pain Points**: Subtle signs of hypoxia or disorientation
- **Wichita Solution**: Voice quality degradation detection

#### 3. Emergency Coordinator
- **Needs**: Triage multiple simultaneous incidents
- **Pain Points**: Limited resources, priority decisions
- **Wichita Solution**: Emotion-based severity scoring

#### 4. Security Analyst
- **Needs**: Detect criminal activity and threats
- **Pain Points**: Coded language, normal words with bad intent
- **Wichita Solution**: Tone and stress analysis beyond words

---

## 5. FUNCTIONAL REQUIREMENTS

### 5.1 Core Features

#### RF Capture & Demodulation
- **MUST** support 1 kHz to 2 GHz frequency range
- **MUST** handle multiple modulation types (AM, FM, SSB)
- **MUST** capture with 14-bit ADC quality (RSPdx-R2)
- **SHOULD** support multiple simultaneous frequencies
- **COULD** integrate with multiple SDR hardware types

#### S2S Emotional Analysis
- **MUST** detect stress levels (0-100% scale)
- **MUST** identify panic, exhaustion, confusion
- **MUST** preserve accent and language
- **MUST** process in real-time (<500ms)
- **SHOULD** track voice degradation over time
- **COULD** build voice fingerprint database

#### Alert System
- **MUST** trigger on emotion thresholds
- **MUST** provide audio playback with analysis
- **MUST** show geographic location (if determinable)
- **SHOULD** integrate with emergency services
- **COULD** predict escalation patterns

### 5.2 User Interface Requirements

#### Real-time Dashboard
- **MUST** show emotion meters (stress, panic, exhaustion)
- **MUST** display current frequency and modulation
- **MUST** provide audio playback controls
- **SHOULD** show emotion history graph
- **COULD** render 3D emotion space

#### Geographic Display
- **MUST** plot alerts on Malta map
- **MUST** show emotion heatmap overlay
- **SHOULD** track vessel/aircraft paths
- **COULD** predict distress zones

#### Alert Timeline
- **MUST** list all alerts chronologically
- **MUST** color-code by severity
- **MUST** link to audio recordings
- **SHOULD** show emotion context
- **COULD** cluster related events

---

## 6. NON-FUNCTIONAL REQUIREMENTS

### Performance
- **Latency**: <500ms from audio capture to emotion analysis
- **Throughput**: Process 10+ audio streams simultaneously
- **Storage**: 30 days of audio retention (configurable)
- **Availability**: 99.9% uptime

### Scalability
- **Horizontal scaling** for multiple frequency monitoring
- **Cloud-ready** deployment architecture
- **API rate limiting** for S2S calls
- **Efficient audio buffering** (ring buffer design)

### Security & Privacy
- **Encrypted** audio storage
- **GDPR compliant** data retention
- **Access control** for sensitive features
- **Audit logging** for all system actions

### Reliability
- **Automatic recovery** from SDR disconnection
- **Redundant** S2S API endpoints
- **Fallback** to traditional analysis if S2S unavailable
- **Data backup** every 6 hours

---

## 7. TECHNICAL SPECIFICATIONS

### Hardware Requirements
- **Primary SDR**: RSPdx-R2 (14-bit, 1kHz-2GHz)
- **Backup SDR**: HackRF One (8-bit, 1MHz-6GHz)
- **Computer**: Mac Mini M2 (minimum 16GB RAM)
- **Storage**: 1TB SSD for audio retention

### Software Stack
```yaml
RF Layer:
  - SDR++: v1.2.1 (nightly build)
  - SDRplay API: v3.15.1
  
Audio Processing:
  - Python: 3.11+
  - NumPy/SciPy: Latest
  - PyAudio: 0.2.11
  
S2S Integration:
  - OpenAI Realtime SDK: @openai/realtime-api-beta
  - Node.js: 18+ (for TypeScript SDK)
  - WebSocket: For streaming
  
Web Interface:
  - React: 18+ (for dashboard)
  - WebGL: For visualizations
  - Leaflet: For mapping
  - Chart.js: For graphs
  
Backend:
  - FastAPI: For REST API
  - PostgreSQL: For alert storage
  - Redis: For real-time caching
```

### API Integrations
- **OpenAI S2S API**: Emotional intelligence
- **ElevenLabs**: Audio enhancement (backup)
- **Mapbox/Leaflet**: Geographic plotting
- **Twilio**: Emergency notifications

---

## 8. USER STORIES

### Critical Path Stories

1. **As a Coast Guard operator, I need to be alerted when someone is in distress even if they don't explicitly say so, so that I can respond to emergencies where the person is unable to call for help properly.**

2. **As an Air Traffic Controller, I need to detect when a pilot is becoming hypoxic or disoriented, so that I can provide immediate assistance before the situation becomes critical.**

3. **As a Security Analyst, I need to detect threatening behavior through voice stress analysis, so that I can identify potential criminal activity before it occurs.**

### Enhancement Stories

4. **As an Emergency Coordinator, I need to see emotion levels across all monitored frequencies on a map, so that I can allocate resources to the highest priority incidents.**

5. **As a System Administrator, I need to configure emotion detection thresholds, so that I can tune the system for different operational scenarios.**

---

## 9. SUCCESS METRICS

### Primary KPIs
- **Lives Saved**: Track successful interventions
- **Threats Detected**: Criminal activities prevented
- **Response Time**: Average time to alert generation
- **Detection Accuracy**: True positive rate >95%

### Secondary Metrics
- **Emotion Detection Rate**: Emotions analyzed per second
- **Language Accuracy**: Correct language identification >90%
- **System Uptime**: Maintain 99.9% availability
- **Alert Quality**: False positive rate <5%

---

## 10. DEVELOPMENT PHASES

### Phase 1: Foundation (Week 1-2)
- Install OpenAI S2S SDK
- Create audio pipeline from SDR++
- Basic emotion detection
- Simple alert system

### Phase 2: Intelligence (Week 3-4)
- Multi-agent system implementation
- Language/accent handling
- Emotion threshold tuning
- Geographic plotting

### Phase 3: Interface (Week 5-6)
- Real-time dashboard
- Emotion visualization
- Alert timeline
- Audio playback

### Phase 4: Integration (Week 7-8)
- Emergency service connectivity
- Historical analysis
- Pattern recognition
- Predictive modeling

### Phase 5: Deployment (Week 9-10)
- Production deployment
- Monitoring setup
- Training materials
- Operational handoff

---

## 11. RISKS & MITIGATIONS

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| S2S API latency | High | Medium | Implement caching and fallback |
| False positives | High | Medium | Tunable thresholds, human review |
| Language confusion | Medium | Low | Multi-agent specialization |
| SDR disconnection | High | Low | Automatic reconnection logic |

### Operational Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| Privacy concerns | High | Medium | Clear data retention policy |
| Alert fatigue | Medium | Medium | Smart filtering, priority levels |
| Training required | Medium | High | Comprehensive documentation |

---

## 12. APPENDICES

### A. Maltese Frequency Allocations
- Maritime VHF: 156-162 MHz
- Aviation: 118-137 MHz  
- Emergency: 121.5 MHz, 156.8 MHz

### B. Emotion Detection Thresholds
- Critical Stress: >80%
- Panic Emergency: >90%
- Exhaustion Warning: >70%

### C. Language Support
- Primary: English, Maltese
- Secondary: Italian, Arabic
- Code-switching: Supported

---

## APPROVAL

**Product Owner**: Matt Carp  
**Technical Lead**: Wichita System  
**Date**: September 2025  
**Status**: Approved for Development

---

*This PRD represents the next evolution of RF forensics - where emotional intelligence meets radio surveillance to save lives and prevent crime.*

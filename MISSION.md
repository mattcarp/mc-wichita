# RF DIGITAL FORENSICS TOOLKIT - MISSION STATEMENT

## PROJECT IDENTITY - KENNETH

**THE IMMUTABLE CORE:**
- **Name:** Kenneth
- **Mission:** Goals: 1. Detect bad actors, 2. Help those in distress

These two elements define the project and must NEVER be changed in any UI, demo, or documentation.

## THE DUAL MISSION

### 🚨 MISSION 1: CATCH BAD GUYS
**Objective:** Detect and prevent harm before it happens

**What We Listen For:**
- Threatening language or intent to harm
- Criminal coordination or planning  
- Illegal activities being discussed
- Suspicious patterns of communication
- Coded language indicating malicious intent

**Detection Methods:**
- Sentiment analysis (anger, aggression, threat indicators)
- Keyword detection across all languages
- Pattern recognition (unusual timing, frequency hopping)
- Voice stress analysis
- Behavioral anomalies

### 🆘 MISSION 2: SAVE LIVES
**Objective:** Find people in distress and get them help - BEYOND just emergency calls

**What We Listen For:**

**EXPLICIT DISTRESS:**
- Direct emergency calls (MAYDAY, PAN-PAN, SOS)
- Medical emergencies being described
- "Help" in any language or dialect

**IMPLICIT DISTRESS PATTERNS:**
- **Confusion/Disorientation:** "Where am I?", "I can't find...", repeated location requests
- **Exhaustion:** Slurred speech, long pauses, breathing difficulties in transmission
- **Panic Without Words:** Heavy breathing, crying, whimpering, screaming
- **Gradual Deterioration:** Voice getting weaker over multiple transmissions
- **Mechanical Problems:** "Engine won't start", "Taking on water", "Losing altitude"
- **Resource Depletion:** "Running out of fuel/food/water/battery"
- **Isolation Indicators:** "Haven't seen anyone in days", "Radio is my only contact"

**BEHAVIORAL ANOMALIES:**
- **Sudden Silence:** Regular check-ins that suddenly stop
- **Off-Schedule Transmissions:** Fishing boat calling at 3am instead of usual 6pm
- **Location Drift:** Vessel/person reporting from unexpected coordinates
- **Repeated Attempts:** Same message sent multiple times (desperation)
- **Channel Hopping:** Trying multiple frequencies to find help
- **Weakening Signal:** Progressive signal degradation (dying battery/increasing distance)

**INDIRECT INDICATORS:**
- **Child's Voice:** Children on maritime/aviation frequencies
- **Wrong Language:** Tourist speaking English on local-only frequency
- **Code Words:** Family/cultural distress phrases ("red sunset" = danger)
- **Background Sounds:** Alarms, water sounds, wind/storm, crying children
- **Time Criticality:** "Before dark", "High tide coming", "Storm approaching"

**PSYCHOLOGICAL PATTERNS:**
- **Bargaining:** "If someone can hear this..."
- **Resignation:** "This might be my last transmission"
- **Anger/Frustration:** Escalating emotional state over time
- **Confusion:** Repeating questions, forgetting previous exchanges
- **Hypothermia Signs:** Slurred speech, illogical statements
- **Dehydration/Heatstroke:** Confusion, aggression, disorientation

**SOCIAL DISTRESS:**
- **Domestic Violence:** Coded requests, whispered transmissions
- **Human Trafficking:** Multiple voices, fearful tones, controlled speech
- **Elderly Isolation:** Confusion about technology, health concerns
- **Mental Health Crisis:** Suicidal ideation, paranoid behavior
- **Lost Children:** Young voices on adult frequencies

**TECHNICAL INDICATORS:**
- **Morse Code SOS:** Even if voice comms work
- **EPIRB/PLB Activation:** 406 MHz beacon detection
- **AIS Anomalies:** Vessel track showing circles, drift, or stoppage
- **Transponder Issues:** Aircraft squawking 7700 (emergency)
- **DSC Distress:** Digital Selective Calling automated alerts

**Detection Methods:**
- **AI Sentiment Analysis:** Fear, panic, desperation, resignation
- **Voice Biometrics:** Stress, fatigue, medical conditions
- **Pattern Recognition:** Deviation from normal behavior
- **Acoustic Analysis:** Background sound classification
- **Temporal Analysis:** Transmission timing/frequency changes
- **Cross-Reference:** Multiple weak indicators = strong signal
- **Predictive Modeling:** "This pattern leads to emergency in 2 hours"

## TECHNICAL APPROACH

### Language Agnostic Detection
1. **Start with Maltese** (hardest case) → Master all languages
2. **Multi-language pipeline:**
   - RF Capture (HackRF)
   - Noise Removal (ElevenLabs)
   - Transcription (Whisper/Multiple engines)
   - Translation (to English for analysis)
   - Sentiment/Intent Analysis
   - Alert Generation

### Coverage
- **Frequency Range:** 1 MHz - 6 GHz (full HackRF spectrum)
- **Location:** Malta (Mediterranean crossroads)
- **Languages:** ALL (starting with Maltese, Arabic, Italian, English)
- **Sources:** 
  - Marine VHF (156-162 MHz)
  - Aviation (108-137 MHz)
  - Emergency frequencies (121.5, 243.0, 406 MHz)
  - Amateur radio bands
  - Commercial radio (FM/AM)
  - Cellular bands
  - Satellite downlinks

### Alert System
**Phase 1:** SMS to operator
**Phase 2:** Multi-channel alerts (SMS, email, API webhooks)
**Phase 3:** Direct integration with emergency services

## WHY THIS MATTERS

From our position in Malta, we sit at the crossroads of:
- Mediterranean maritime traffic
- North Africa ↔ Europe migration routes  
- Major shipping lanes
- International aviation corridors

**We can hear:**
- Boats in distress before they sink
- People calling for help in remote areas
- Criminal activities being planned
- Emergency beacons that others might miss

**We can save lives and stop bad things from happening.**

## SUCCESS METRICS

### Bad Guy Detection
- Threats identified before execution
- Criminal activities disrupted
- Response time < 5 minutes from detection

### Life Saving
- Distress calls responded to
- People rescued
- Emergency response time reduced
- Lives saved

## ETHICAL FRAMEWORK

1. **Privacy:** We don't record or store routine communications
2. **Focus:** Only flag threats and emergencies
3. **Transparency:** Clear documentation of capabilities
4. **Legal:** Comply with all local/international laws
5. **Humanitarian:** Life-saving always takes priority

## THE VISION

Build a system that can:
- Understand a cry for help in ANY language
- Detect malicious intent regardless of code words
- Work through noise, interference, and weak signals
- Provide actionable intelligence in real-time
- Scale from Malta to global deployment

**Starting with the hardest problem (Maltese in noisy RF) means we build something that works EVERYWHERE.**

---

*"If we can detect a Maltese fisherman in distress through static, we can detect anything."*
*"If we can identify threats in Arabic/Maltese code-switching, we can identify threats anywhere."*

This is not mass surveillance. This is targeted detection of:
1. **People who want to hurt others**
2. **People who need help**

Everything else is noise we ignore.
---

## ORIGIN & ETHOS — Signal Hunters

*Pulled in from the "Signal Ethics" stego page (archived at branch `archive/signal-ethics`).*

**Signal Hunters** — *Les chasseurs de signaux. Dans le noir.*

**Kenneth** = the RF hunter, "the ears in the static." Named for the R.E.M. song
"What's the frequency, Kenneth?" — itself named for an unsolved mystery (a man
attacked Dan Rather asking that question; nobody knew why). We're still asking —
but now we're finding answers.

> In the noise, there are signals. In the dark, there are people. We find both.
> Some are calling for help. Some are hiding harm. We find both.

### The four domains

| Domain | What we surface |
|---|---|
| RF noise | distress calls nobody else hears |
| Market data | fraud patterns hiding in transaction chaos |
| Classified ads | the fingerprints of trafficking networks |
| Social velocity | disasters before they break |

### The cast (architecture metaphor)

- **Claudia** — *grande sœur* — the architect
- **Claudette** — *petite sœur* — the searcher
- **Kenneth** — the hunter — the listener / ears in the static
- **Mattie** — *le cœur* — the one who asked: "What if we could find the helpers and stop the harm?"

### Origin

Malta — **35.8989° N, 14.5146° E** — where Signal Hunters began.

### Ethos (Shannon)

- "The fundamental problem of communication is that of reproducing at one point either
  exactly or approximately a message selected at another point." — Claude Shannon, 1948
- "Information is the resolution of uncertainty." — H = −Σ p(x) log₂ p(x)
- The signal is in the noise.

### Provenance — the wire, the frequency, the year

Five transmissions, one lineage:

- **1522** — Pigafetta's journal circumnavigates; Magellan does not. The sender
  doesn't always survive the transmission. The log came home without the captain —
  the message reproduced at another point, exactly or approximately, 426 years
  before Shannon wrote the sentence.
- **1912** — the Marconi room teaches the world SOS discipline, and the law that
  followed wrote listening into statute: twice an hour on 500 kHz, three minutes
  of mandatory silence so weak distress calls could be heard. Kenneth is a
  silence period that never ends.
- **1948** — Shannon, Bell Labs: every noisy channel has a capacity, and beneath
  it, any message can be recovered. Noise doesn't doom the signal; it taxes it.
- **1968** — Jimmy Webb writes "Wichita Lineman" for Glen Campbell: a man on a
  wire who hears more than the line is carrying. *I can hear you through the
  whine.* The public face of this project — **Wichita** on sottosound.com —
  carries his name.
- **Now** — Kenneth listens from a rooftop in Malta for the second signal inside
  the first: the distress encoded in a voice that says "I'm fine." More
  information in the channel than the sender meant to transmit. Shannon proved
  it could be recovered. The lineman heard it. We decode it.

The song asks *what's the frequency*; the theory answers *what's the capacity*;
the mission is everything the channel carries below the words. Sotto voce.

The chip log measured the ship; the logbook remembered the voyage; Kenneth logs
the boats that file nothing.

*The kind army is recruiting.*

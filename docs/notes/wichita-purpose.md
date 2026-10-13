# Wichita: purpose (updated 2026-10-13)

Wichita (mattcarp/mc-wichita) exists to help people who are vulnerable, in their time of need, anywhere a human voice can be heard on the radio: in the air, on land and at sea. It is not limited to marine radio and is not built around the word "mayday". Any band where people speak counts: aviation, marine VHF, land mobile, emergency services, amateur, PMR446.

AI analysis of the human voice is at the core. Wichita listens to how people speak, not only what they say. Voice features (pitch variance, zero-crossing rate, speech rate, loudness) feed a 0 to 100 stress score, alongside transcription (faster-whisper; Maltese, English, Italian, Arabic) and distress keywords. A person reviews every alert; nothing is acted on automatically. Wichita also listens for bad actors (threats, coordination, coded intent), per the two fixed goals in MISSION.md.

Positioning (AIS, ADS-B) is secondary context. It is available from other sources and is not the point.

Hardware and place: receive-only (it never transmits). An SDRplay RSPdx-R2 (14-bit, 1 kHz to 2 GHz) on a rooftop antenna, built and listening in Valletta, Malta. The dashboard is served from Hetzner at wichitawire.com.

Audience: technologists and technically minded potential investors. Public material should show the signal chain, hardware, bands, decoders, voice features and pipeline openly.

Wichita is NOT about loneliness; that is the Hank project (mattcarp/mc-homecompanion). The name comes from Glen Campbell's "Wichita Lineman": the man on the wire who hears more than the line carries.

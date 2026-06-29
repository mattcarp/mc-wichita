# RF Digital Forensics Toolkit - Project Overview

## Project Location
`/Users/matt/Documents/projects/RF-Digital-Forensics-Toolkit/`

## Hardware
- **HackRF One** (Serial: ...2e2a5353, Revision: r10)
- **PortaPack H2/H4** with Mayhem firmware
- **Location**: Victoria, Gozo, Malta (Mediterranean RF intelligence position)

## Project Structure

### Core Scripts
- `fm_station_finder.sh` - Scans FM band for active stations
- `fm_demodulator_malta.py` - Demodulates captured FM signals
- `malta_fm_scanner.py` - Malta-specific FM station scanner
- `simple_fm_malta.py` - Simple FM receiver for Magic Malta
- `aviation_scanner.sh` - Aviation frequency scanner
- `signal_hunter.py` - General signal detection
- `find_best_signal.py` - Signal strength analyzer

### Source Code (`/src`)
- `rf_forensics_core.py` - Main forensics engine
- `hackrf_interface.py` - HackRF hardware interface
- `tinysa_interface.py` - TinySA spectrum analyzer interface

### API & Server
- `api_server.py` - FastAPI server for RF operations
- `start_api.sh` - API server launcher

### MCP Server Agents (`/mcp_server`)
- Taskmaster AI orchestration
- RF analysis agents
- Threat detection systems

### Documentation (`/docs`)
- `hardware-connection.md` - Complete HackRF connection guide
- `CLAUDE.md` - Claude AI integration notes
- `TASKMASTER_TODO.md` - Project roadmap

### Tools (`/tools`)
- `switch_to_hackrf_mode.py` - Switch between USB/PortaPack modes
- `test_hackrf_usb.py` - HackRF connection tester

## Malta FM Stations (Strong in Gozo)
1. **103.7 MHz - Magic Malta** ⭐ (Strongest signal)
2. **91.0 MHz - Calypso Radio** (Local Gozo station)
3. **89.7 MHz - Radio Malta**
4. **101.0 MHz - Bay**
5. **100.3 MHz - NET FM**

## Key Achievements
✅ Successfully connected HackRF in both USB and PortaPack modes
✅ Captured and demodulated FM signals from Malta
✅ **FIRST VOICE INTERCEPT: Heard Maltese transmission (Aug 28, 2025)**
✅ **CONFIRMED STRONG SIGNALS: -0.4 to 2.6 dB from Valletta rooftop**
✅ Created comprehensive scanning tools for Mediterranean signals
✅ Built Python-based demodulation pipeline
✅ Documented all hardware connection states
✅ Detected 10+ active digital signals (AIS, ADS-B, ACARS, etc.)

## Next Steps
- [ ] Implement maritime AIS signal decoder
- [ ] Add aviation ADS-B tracking
- [ ] Build threat detection for rogue transmitters
- [ ] Create ML-based signal classification
- [ ] Integrate Claude Opus 4.1 for signal analysis

## Quick Commands
```bash
# Check HackRF connection
hackrf_info

# Scan FM stations
python3 malta_fm_scanner.py

# Demodulate captured FM
python3 fm_demodulator_malta.py

# Switch to USB mode
python3 tools/switch_to_hackrf_mode.py

# Start API server
./start_api.sh
```

## Notes
- Permission issues on macOS require careful handling
- PortaPack mode uses serial: `/dev/cu.usbmodemTransceiver1`
- USB mode allows direct SDR software control
- Victoria, Gozo provides excellent Mediterranean signal coverage

# RF Digital Forensics Toolkit - Installation Guide

Complete setup guide for Mac Mini and other macOS systems.

## 1. Clone the Repository
```bash
git clone https://github.com/mattcarp/RF-Digital-Forensics-Toolkit.git
cd RF-Digital-Forensics-Toolkit
```

## 2. Install Dependencies

### Python Dependencies
```bash
# Install Python packages
pip3 install -r requirements.txt
```

### Hardware Dependencies (macOS)
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install HackRF tools
brew install hackrf

# Install additional RF tools
brew install gnuradio
brew install sox  # For audio processing
```

## 3. Frontend Setup (Wichita WebSDR)
```bash
cd wichita-websdr
npm install
npm run dev  # Runs on port 4000
```

## 4. API Server Setup
```bash
# Make scripts executable
chmod +x start_api.sh
chmod +x *.sh

# Start API server
./start_api.sh
# Or directly: python3 -m uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

## 5. Hardware Verification
```bash
# Test HackRF connection
hackrf_info

# If you have PortaPack, check serial connection
ls /dev/cu.* | grep -i transceiver
```

## 6. Environment Variables
```bash
# Add to ~/.zshrc or ~/.bash_profile
export ELEVENLABS_API_KEY='your_key_here'  # Get from elevenlabs.io
```

## Hardware Requirements
- HackRF One with PortaPack H2/H4 (Mayhem firmware)
- tinySA Ultra+ Spectrum Analyzer (100kHz - 7.3GHz)
- Mac with USB ports for hardware connections

## Verification Commands
```bash
# Test hardware connections
python tests/test_hardware.py

# Start API server (runs on port 8000, includes Swagger UI)
./start_api.sh

# Frontend Development (ALWAYS use port 4000, not 3000)
cd wichita-websdr
npm run dev

# Run tests
pytest tests/
```

## API Documentation
When server is running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI spec: http://localhost:8000/openapi.json
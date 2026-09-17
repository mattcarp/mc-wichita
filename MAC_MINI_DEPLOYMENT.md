# Mac Mini Deployment Guide

## Quick Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mattcarp/RF-Digital-Forensics-Toolkit.git
   cd RF-Digital-Forensics-Toolkit
   ```

2. **Install Python dependencies:**
   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. **Install Node.js dependencies:**
   ```bash
   npm install
   cd wichita-websdr && npm install
   ```

4. **Hardware Setup (SDRplay):**
   ```bash
   # Install SDRplay API from www.sdrplay.com/downloads/
   brew install soapysdr soapysdrplay3
   
   # Test connection
   SoapySDRUtil --find
   ```

## Running the System

### API Server (Port 8000)
```bash
python3 api_server.py
# Or use the script:
./start_api.sh
```

### Frontend (Port 4000)
```bash
cd wichita-websdr
npm run build
npm start
```

## Key Features Ready
- ✅ RF signal capture and analysis
- ✅ Maritime/Aviation monitoring
- ✅ ElevenLabs audio enhancement integration
- ✅ FastAPI server with Swagger docs
- ✅ Next.js frontend with spectrum display
- ✅ Hardware abstraction layer

## Access Points
- API Documentation: http://localhost:8000/docs
- Frontend Dashboard: http://localhost:4000
- Wichita WebSDR: http://localhost:4000

## Hardware Support
- SDRplay RSPdx/RSPduo (primary)
- HackRF One (secondary)
- tinySA Ultra+ (spectrum analyzer)

System is ready for deployment with minimal configuration needed.
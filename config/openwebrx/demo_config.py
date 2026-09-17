# Minimal Wichita Demo Configuration
# For testing without HackRF hardware

receiver_name = "Wichita RF Forensics - Demo Mode"
receiver_location = "Victoria, Gozo, Malta"
receiver_admin = "Wichita System"
receiver_gps = (35.8997, 14.5136)

web_port = 8073
max_clients = 10

# Demo SDR configuration (no hardware needed)
sdrs = {
    "rtlsdr": {
        "name": "Demo SDR",
        "type": "rtl_sdr_soapy",
        "ppm": 0,
        "profiles": {
            "Demo": {
                "name": "Demo Profile",
                "center_freq": 103700000,
                "samp_rate": 2400000,
                "start_freq": 103700000,
                "start_mod": "wfm",
            }
        },
    },
}

# Disable services for demo
services_enabled = False
background_decoding = False

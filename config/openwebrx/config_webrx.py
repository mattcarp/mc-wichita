# Wichita - RF Forensics Configuration for Malta
# OpenWebRX+ Configuration
# Mission: Catching Bad Guys | Saving Lives

receivers = {
    "Wichita_Malta_HackRF": {
        "type": "hackrf",
        "ppm": 0,
        "device": "0",  # First HackRF device
        "services": ["ais", "packet", "pocsag"],
        "profiles": {
            "Marine_Emergency": {
                "name": "Marine VHF Emergency",
                "center_freq": 156800000,  # Channel 16
                "samp_rate": 2400000,
                "start_freq": 156800000,
                "start_mod": "nfm",
                "waterfall_auto_level_margin": 10
            },
            "Aviation_Emergency": {
                "name": "Aviation Emergency",
                "center_freq": 121500000,
                "samp_rate": 2400000,
                "start_freq": 121500000,
                "start_mod": "am",
                "waterfall_auto_level_margin": 10
            },
            "AIS_1": {
                "name": "AIS Channel 1",
                "center_freq": 161975000,
                "samp_rate": 2400000,
                "start_freq": 161975000,
                "start_mod": "nfm",
                "waterfall_auto_level_margin": 10
            },
            "AIS_2": {
                "name": "AIS Channel 2",
                "center_freq": 162025000,
                "samp_rate": 2400000,
                "start_freq": 162025000,
                "start_mod": "nfm",
                "waterfall_auto_level_margin": 10
            },
            "EPIRB_406": {
                "name": "EPIRB 406 MHz",
                "center_freq": 406028000,
                "samp_rate": 2400000,
                "start_freq": 406028000,
                "start_mod": "nfm",
                "waterfall_auto_level_margin": 10
            },
            "Amateur_2m_Calling": {
                "name": "Amateur 2m Calling",
                "center_freq": 146520000,
                "samp_rate": 2400000,
                "start_freq": 146520000,
                "start_mod": "nfm",
                "waterfall_auto_level_margin": 10
            },
            "Amateur_70cm_Calling": {
                "name": "Amateur 70cm Calling",
                "center_freq": 446000000,
                "samp_rate": 2400000,
                "start_freq": 446000000,
                "start_mod": "nfm",
                "waterfall_auto_level_margin": 10
            },
            "Malta_FM": {
                "name": "Malta FM Radio",
                "center_freq": 103700000,  # Magic Malta
                "samp_rate": 2400000,
                "start_freq": 103700000,
                "start_mod": "wfm",
                "waterfall_auto_level_margin": 10
            },
            "Wide_Scan": {
                "name": "Wide Band Scan",
                "center_freq": 145000000,
                "samp_rate": 20000000,  # Max for HackRF
                "start_freq": 145000000,
                "start_mod": "usb",
                "waterfall_auto_level_margin": 10
            }
        }
    }
}

# General settings
general_settings = {
    "receiver_name": "Wichita RF Forensics - Malta",
    "receiver_location": "Victoria, Gozo, Malta",
    "receiver_coordinates": [36.0444, 14.2401],  # Gozo coordinates
    "receiver_admin": "Wichita Project",
    "receiver_description": "Mission-Critical RF Monitoring - Mediterranean",
    "photo_title": "Wichita - Catching Bad Guys | Saving Lives",
    "photo_description": "RF Digital Forensics Platform"
}

# Waterfall settings
waterfall_scheme = "GoogleTurboWaterfall"  # Good visibility for signals
waterfall_min_level = -120
waterfall_max_level = -20
waterfall_auto_level_default_mode = "continuous"

# Audio settings
audio_compression = "none"  # We want raw audio for forensics
fft_fps = 30
fft_size = 8192
fft_overlap_factor = 0.5

# Server settings
server_hostname = "localhost"
web_port = 8073
max_clients = 10

# Map settings (optional)
map_position_retention_time = 2 * 60 * 60  # 2 hours

"""Shared scan frequency configuration for Wichita scanners."""

from __future__ import annotations

from typing import Dict, List


SCAN_BANDS: List[Dict[str, object]] = [
    {
        "name": "EPIRB 406",
        "frequency_mhz": 406.028,
        "demod_mode": "nfm",
        "autonomous_key": "EPIRB_406.028",
        "voice_key": "EPIRB 406",
    },
    {
        "name": "AIS 1",
        "frequency_mhz": 161.975,
        "demod_mode": "nfm",
        "autonomous_key": "AIS_161.975",
        "voice_key": "AIS 1",
    },
    {
        "name": "AIS 2",
        "frequency_mhz": 162.025,
        "demod_mode": "nfm",
        "autonomous_key": "AIS_162.025",
        "voice_key": "AIS 2",
    },
    {
        "name": "Marine CH16",
        "frequency_mhz": 156.800,
        "demod_mode": "nfm",
        "autonomous_key": "CH16",
        "voice_key": "CH16 Emergency",
    },
    {
        "name": "Marine CH09",
        "frequency_mhz": 156.450,
        "demod_mode": "nfm",
        "autonomous_key": "CH09",
        "voice_key": "CH09 Calling",
    },
    {
        "name": "Marine CH13",
        "frequency_mhz": 156.650,
        "demod_mode": "nfm",
        "autonomous_key": "CH13",
        "voice_key": "CH13 Bridge",
    },
    {
        "name": "Marine CH22A",
        "frequency_mhz": 157.100,
        "demod_mode": "nfm",
        "autonomous_key": "CH22A",
        "voice_key": "CH22A Coast Guard",
    },
    {
        "name": "Amateur 6m Calling",
        "frequency_mhz": 52.525,
        "demod_mode": "nfm",
        "autonomous_key": "HAM_6M_52.525",
        "voice_key": "Amateur 6m Calling",
    },
    {
        "name": "Amateur 2m Packet",
        "frequency_mhz": 144.800,
        "demod_mode": "nfm",
        "autonomous_key": "HAM_2M_144.8",
        "voice_key": "Amateur 2m Packet",
    },
    {
        "name": "Amateur 2m Calling",
        "frequency_mhz": 146.520,
        "demod_mode": "nfm",
        "autonomous_key": "HAM_2M_146.52",
        "voice_key": "Amateur 2m Calling",
    },
    {
        "name": "Amateur 1.25m Calling",
        "frequency_mhz": 223.500,
        "demod_mode": "nfm",
        "autonomous_key": "HAM_125CM_223.5",
        "voice_key": "Amateur 1.25m Calling",
    },
    {
        "name": "Amateur 70cm Calling",
        "frequency_mhz": 446.000,
        "demod_mode": "nfm",
        "autonomous_key": "HAM_70CM_446.0",
        "voice_key": "Amateur 70cm Calling",
    },
]


def load_scan_config() -> Dict[str, object]:
    """Return a serializable scan configuration dictionary."""
    return {"bands": [dict(entry) for entry in SCAN_BANDS]}


def demod_mode_by_frequency_hz() -> Dict[int, str]:
    """Map configured frequencies in Hz to demodulation mode."""
    return {
        int(round(float(entry["frequency_mhz"]) * 1e6)): str(entry["demod_mode"])
        for entry in SCAN_BANDS
    }

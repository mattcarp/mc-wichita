#!/usr/bin/env python3
"""
RF Signal Detector for Kenneth — Properly calibrated for SDRplay RSPdx-R2
Uses raw IQ analysis BEFORE FM demod to distinguish signal from noise.
"""

import numpy as np
from scipy import signal as sig
import logging

logger = logging.getLogger(__name__)

# Noise floor baselines (calibrated 2026-02-17, SDRplay RSPdx-R2, gain=30)
NOISE_BASELINE = {
    'iq_rms': 0.003,
    'spectral_flatness': 0.61,
    'iq_dynamic_range_dB': 6.5,
    'audio_voice_ratio': 0.13,
    'audio_dynamic_range_dB': 1.4,
}

# Thresholds for signal detection (must exceed noise baseline significantly)
SIGNAL_THRESHOLDS = {
    'iq_dynamic_range_dB': 12.0,      # Noise is ~6.5, signal should be >12
    'spectral_flatness_max': 0.45,     # Noise is ~0.61, signal should be <0.45
    'iq_rms_min': 0.001,  # Lowered — manual gain keeps absolute level low               # Must be above noise floor
}

# Thresholds for voice detection (applied AFTER signal detection)
VOICE_THRESHOLDS = {
    'audio_voice_ratio_min': 0.25,     # Noise baseline is 0.13, voice should be >0.25
    'audio_dynamic_range_dB': 5.0,     # Noise is ~1.4, voice should have >5 dB range
    'syllable_rate_min': 2.0,
    'syllable_rate_max': 10.0,
}


def analyze_iq_for_signal(iq_data, sample_rate=2048000):
    """
    Analyze raw IQ data to determine if a real signal is present.
    Returns: (has_signal, signal_strength, details)
    """
    rms = np.sqrt(np.mean(np.abs(iq_data)**2))
    peak = np.max(np.abs(iq_data))
    
    # Spectral flatness — noise is flat (~0.61), signal has peaks (<0.4)
    freqs, psd = sig.welch(np.real(iq_data), sample_rate, nperseg=4096)
    psd_norm = psd / (np.sum(psd) + 1e-20)
    spectral_flatness = np.exp(np.mean(np.log(psd_norm + 1e-20))) / (np.mean(psd_norm) + 1e-20)
    
    # Dynamic range of power spectrum
    psd_db = 10 * np.log10(psd + 1e-20)
    dynamic_range = np.max(psd_db) - np.median(psd_db)
    
    details = {
        'iq_rms': float(rms),
        'iq_peak': float(peak),
        'spectral_flatness': float(spectral_flatness),
        'iq_dynamic_range_dB': float(dynamic_range),
    }
    
    # Signal detection logic
    has_signal = (
        dynamic_range > SIGNAL_THRESHOLDS['iq_dynamic_range_dB'] and
        spectral_flatness < SIGNAL_THRESHOLDS['spectral_flatness_max'] and
        rms > SIGNAL_THRESHOLDS['iq_rms_min']
    )
    
    # Signal strength: how far above noise baseline
    dr_excess = max(0, dynamic_range - NOISE_BASELINE['iq_dynamic_range_dB'])
    signal_strength = min(1.0, dr_excess / 20.0)  # Normalize to 0-1
    
    details['has_signal'] = has_signal
    details['signal_strength'] = float(signal_strength)
    
    return has_signal, signal_strength, details


def analyze_audio_for_voice(audio_48k, sample_rate=48000, modulation="fm"):
    """
    Analyze demodulated audio for voice activity.
    Only call this AFTER signal detection confirms a real signal exists.
    Returns: (has_voice, voice_score, details)
    """
    if len(audio_48k) < 2048:
        return False, 0.0, {'error': 'audio too short'}
    
    details = {}
    
    # Voice band energy ratio
    af, apsd = sig.welch(audio_48k, sample_rate, nperseg=2048)
    voice_mask = (af >= 300) & (af <= 3400)
    total_mask = af > 0
    voice_ratio = np.sum(apsd[voice_mask]) / (np.sum(apsd[total_mask]) + 1e-20)
    details['voice_ratio'] = float(voice_ratio)
    
    # Audio dynamic range
    apsd_db = 10 * np.log10(apsd + 1e-20)
    audio_dr = float(np.max(apsd_db) - np.median(apsd_db))
    details['audio_dynamic_range_dB'] = audio_dr
    
    # Modulation depth (speech is highly modulated)
    envelope = np.abs(sig.hilbert(audio_48k))
    env_mean = np.mean(envelope)
    env_std = np.std(envelope)
    mod_depth = float(env_std / (env_mean + 1e-10))
    details['modulation_depth'] = mod_depth
    
    # Syllabic rate
    try:
        b, a = sig.butter(4, 10/(sample_rate/2), 'low')
        env_smooth = sig.filtfilt(b, a, np.abs(audio_48k))
        peaks, _ = sig.find_peaks(env_smooth, distance=sample_rate//10)
        syllable_rate = float(len(peaks) / (len(audio_48k) / sample_rate))
        details['syllable_rate'] = syllable_rate
        syllable_ok = VOICE_THRESHOLDS['syllable_rate_min'] <= syllable_rate <= VOICE_THRESHOLDS['syllable_rate_max']
    except:
        syllable_rate = 0
        syllable_ok = False
    
    # AM has different energy distribution — lower VR threshold
    vr_threshold = VOICE_THRESHOLDS['audio_voice_ratio_min']
    if modulation == 'am':
        vr_threshold = 0.15  # AM baseline noise ~0.10, voice typically 0.15-0.30

    # Voice detection: ALL conditions must be met
    has_voice = (
        voice_ratio > vr_threshold and
        audio_dr > VOICE_THRESHOLDS['audio_dynamic_range_dB'] and
        syllable_ok
    )
    
    # Voice confidence score
    vr_score = max(0, (voice_ratio - 0.13) / 0.37)  # 0.13=noise, 0.50=strong voice
    dr_score = max(0, (audio_dr - 1.4) / 10.0)       # 1.4=noise, 11.4=strong voice
    voice_score = float(min(1.0, (vr_score + dr_score) / 2))
    
    details['has_voice'] = has_voice
    details['voice_score'] = voice_score
    
    return has_voice, voice_score, details


def fm_demodulate(iq_data, iq_sample_rate=2048000, audio_rate=48000):
    """FM demodulate IQ data to audio"""
    phase = np.unwrap(np.angle(iq_data))
    audio = np.diff(phase)
    audio = audio / (np.max(np.abs(audio)) + 1e-10)
    ratio = audio_rate / iq_sample_rate
    n = int(len(audio) * ratio)
    idx = np.linspace(0, len(audio)-1, n).astype(int)
    return audio[idx].astype(np.float32)



def am_demodulate(iq_data, sample_rate=2048000, audio_rate=48000):
    """AM (envelope) demodulate IQ data to audio -- used for aviation VHF"""
    envelope = np.abs(iq_data).astype(np.float32)
    envelope -= np.mean(envelope)
    max_val = np.max(np.abs(envelope))
    if max_val > 1e-10:
        envelope /= max_val
    ratio = audio_rate / sample_rate
    n = int(len(envelope) * ratio)
    idx = np.linspace(0, len(envelope)-1, n).astype(int)
    return envelope[idx].astype(np.float32)

def full_detection_pipeline(iq_data, sample_rate=2048000, modulation='fm'):
    """
    Complete signal + voice detection pipeline.
    Args:
        modulation: 'fm' (default, maritime VHF) or 'am' (aviation VHF 118-136 MHz)
    Returns: (has_voice, details)
    """
    # Step 1: Is there even a signal?
    has_signal, signal_strength, sig_details = analyze_iq_for_signal(iq_data, sample_rate)

    result = {**sig_details, 'modulation': modulation}

    if not has_signal:
        result['has_voice'] = False
        result['voice_score'] = 0.0
        result['rejection_reason'] = 'no_signal'
        return False, result

    # Step 2: Demodulate — AM for aviation, FM for maritime
    if modulation == 'am':
        audio = am_demodulate(iq_data, sample_rate)
    else:
        audio = fm_demodulate(iq_data, sample_rate)

    # Step 3: Check for voice
    has_voice, voice_score, voice_details = analyze_audio_for_voice(audio, modulation=modulation)
    result.update(voice_details)

    if not has_voice:
        result['rejection_reason'] = 'signal_but_no_voice'

    return has_voice, result

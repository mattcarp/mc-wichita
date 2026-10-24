"""
DSC band detector - auto-detects VHF vs HF/MF DSC signals.
"""

import numpy as np
from typing import Tuple, Dict
from .fsk_demod import demodulate_goertzel
from ..decoding.symbol_decoder import SymbolDecoder
from ..protocol.constants import FORMAT_CODES, SYMBOL_EOS


class DSCBandDetector:
    """
    Detects whether a DSC signal is VHF or HF/MF based on frequency content.
    """

    # VHF DSC parameters (Channel 70 - 156.525 MHz)
    # Per ITU-R M.493: 1300 Hz = bit 1 (mark), 2100 Hz = bit 0 (space)
    VHF_PARAMS = {
        'name': 'VHF',
        'baud_rate': 1200,
        'f_mark': 1300,
        'f_space': 2100,
        'shift': 800,
        'center': 1700
    }

    # HF/MF DSC parameters (2-16 MHz)
    HF_PARAMS = {
        'name': 'HF/MF',
        'baud_rate': 100,
        'f_mark': 1615,  # or 1785
        'f_space': 1385,  # or 1615
        'shift': 170,
        'center': 1500
    }

    # Alternative HF parameters
    HF_ALT_PARAMS = {
        'name': 'HF/MF (alt)',
        'baud_rate': 100,
        'f_mark': 1785,
        'f_space': 1615,
        'shift': 170,
        'center': 1700
    }

    def __init__(self):
        """Initialize band detector."""
        pass

    def detect_band(self, samples: np.ndarray, sample_rate: int) -> Dict:
        """
        Detect which DSC band (VHF or HF/MF) the signal is from.

        Uses a two-stage approach:
        1. Check FFT energy at different frequency pairs
        2. Test actual demodulation quality with symbol validity

        Args:
            samples: Audio samples
            sample_rate: Sample rate in Hz

        Returns:
            Dictionary with detected parameters
        """
        # Stage 1: FFT energy check
        n_fft = min(8192, len(samples))
        fft = np.fft.rfft(samples[:n_fft])
        freqs = np.fft.rfftfreq(n_fft, 1/sample_rate)
        magnitude = np.abs(fft)

        # Check energy at different frequency pairs
        vhf_energy = self._check_energy(freqs, magnitude,
                                        self.VHF_PARAMS['f_space'],
                                        self.VHF_PARAMS['f_mark'])

        hf_energy = self._check_energy(freqs, magnitude,
                                       self.HF_PARAMS['f_space'],
                                       self.HF_PARAMS['f_mark'])

        hf_alt_energy = self._check_energy(freqs, magnitude,
                                           self.HF_ALT_PARAMS['f_space'],
                                           self.HF_ALT_PARAMS['f_mark'])

        energies = {
            'VHF': vhf_energy,
            'HF': hf_energy,
            'HF_ALT': hf_alt_energy
        }

        # Stage 2: Test demodulation quality
        # Use a sample of the audio to test decode quality
        test_samples = samples[:min(len(samples), sample_rate * 5)]  # First 5 seconds

        decoder = SymbolDecoder()
        validities = {}

        for band_name, band_params in [('VHF', self.VHF_PARAMS),
                                       ('HF', self.HF_PARAMS),
                                       ('HF_ALT', self.HF_ALT_PARAMS)]:
            # Demodulate with these parameters
            bitstream = demodulate_goertzel(
                test_samples, sample_rate,
                baud_rate=band_params['baud_rate'],
                f_space=band_params['f_space'],
                f_mark=band_params['f_mark']
            )

            # Try all offsets and scan for actual DSC messages with format codes
            best_score = 0

            for offset in range(min(10, len(bitstream))):
                all_symbols = decoder.decode_stream(bitstream.tolist(), start_offset=offset)

                if len(all_symbols) < 30:
                    continue

                # Scan for sequences that look like DSC messages
                # (start with format code, no EOS too early, good validity)
                for i in range(min(500, len(all_symbols) - 30)):
                    window = all_symbols[i:i+30]
                    syms = [s for s, _ in window]
                    vals = [v for _, v in window]

                    # Check for format code at start
                    if syms[0] in FORMAT_CODES:
                        # Check validity
                        validity = sum(vals) / len(window)

                        # Check no EOS too early
                        eos_early = SYMBOL_EOS in syms[:20]

                        if validity > 0.35 and not eos_early:
                            # This looks like a real message!
                            best_score = max(best_score, validity)

            validities[band_name] = best_score

        # Choose band with best validity (weighted by energy)
        # Validity is primary, energy is secondary tie-breaker
        best_band = max(validities, key=lambda k: (validities[k], energies[k]))

        if best_band == 'VHF':
            params = self.VHF_PARAMS.copy()
        elif best_band == 'HF_ALT':
            params = self.HF_ALT_PARAMS.copy()
        else:
            params = self.HF_PARAMS.copy()

        params['detection_confidence'] = validities[best_band]
        params['all_energies'] = energies
        params['all_validities'] = validities

        return params

    def _check_energy(self, freqs: np.ndarray, magnitude: np.ndarray,
                     f_space: float, f_mark: float, bandwidth: float = 50) -> float:
        """
        Check energy at specific frequency pair.

        Args:
            freqs: Frequency array
            magnitude: FFT magnitude
            f_space: Space frequency
            f_mark: Mark frequency
            bandwidth: Bandwidth to check around each frequency

        Returns:
            Combined energy at both frequencies
        """
        # Find energy around space frequency
        space_mask = (freqs >= f_space - bandwidth) & (freqs <= f_space + bandwidth)
        space_energy = np.sum(magnitude[space_mask])

        # Find energy around mark frequency
        mark_mask = (freqs >= f_mark - bandwidth) & (freqs <= f_mark + bandwidth)
        mark_energy = np.sum(magnitude[mark_mask])

        return space_energy + mark_energy

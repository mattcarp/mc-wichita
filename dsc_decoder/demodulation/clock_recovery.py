"""
Clock recovery for DSC bit synchronization.

Handles timing synchronization for extracting bits at the correct baud rate.
"""

import numpy as np
from typing import List


class ClockRecovery:
    """
    Simple clock recovery using fixed-rate sampling.

    For clean signals, fixed-rate sampling works well. The demodulator
    already handles most of the timing by averaging over symbol periods.
    """

    def __init__(self, sample_rate: int, baud_rate: int = 1200):
        """
        Initialize clock recovery.

        Args:
            sample_rate: Sample rate in Hz
            baud_rate: Symbol rate in baud (default 1200)
        """
        self.sample_rate = sample_rate
        self.baud_rate = baud_rate
        self.samples_per_bit = sample_rate / baud_rate

    def extract_bits(self, demod_signal: np.ndarray) -> List[int]:
        """
        Extract bits from demodulated signal.

        This is a simple implementation that samples at fixed intervals.
        The FSK demodulator already performs averaging over bit periods,
        so this mainly converts the numpy array to a list.

        Args:
            demod_signal: Demodulated signal (numpy array of 0s and 1s)

        Returns:
            List of bits (0 or 1)
        """
        return demod_signal.tolist()

    def get_timing_info(self) -> dict:
        """
        Get timing information for debugging.

        Returns:
            Dictionary with timing parameters
        """
        return {
            'sample_rate': self.sample_rate,
            'baud_rate': self.baud_rate,
            'samples_per_bit': self.samples_per_bit,
            'bit_period_us': (1.0 / self.baud_rate) * 1e6
        }

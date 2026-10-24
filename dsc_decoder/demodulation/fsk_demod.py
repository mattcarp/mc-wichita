"""
FSK demodulation for DSC signals.

Implements Goertzel algorithm and bandpass filter methods for
demodulating 1300 Hz / 2100 Hz FSK signals at 1200 baud.
"""

import numpy as np
from scipy.signal import butter, sosfilt
from typing import List


def goertzel_filter(samples: np.ndarray, target_freq: float, sample_rate: int) -> float:
    """
    Goertzel algorithm for efficient single-frequency DFT.

    More efficient than FFT when only interested in a single frequency component.

    Args:
        samples: Input signal samples
        target_freq: Frequency to detect (Hz)
        sample_rate: Sample rate (Hz)

    Returns:
        Power (magnitude squared) at the target frequency
    """
    N = len(samples)
    k = int(0.5 + (N * target_freq / sample_rate))
    omega = (2.0 * np.pi * k) / N
    cosine = np.cos(omega)
    coeff = 2.0 * cosine

    # Initialize state variables
    s_prev = 0.0
    s_prev2 = 0.0

    # Process all samples
    for sample in samples:
        s = sample + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s

    # Calculate power
    power = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2

    return power


def demodulate_goertzel(samples: np.ndarray, sample_rate: int,
                        baud_rate: int = 1200,
                        f_space: float = 2100.0,
                        f_mark: float = 1300.0) -> np.ndarray:
    """
    Demodulate FSK signal using Goertzel algorithm.

    Args:
        samples: Audio samples (mono, float32, normalized)
        sample_rate: Sample rate in Hz
        baud_rate: Symbol rate in baud (default 1200)
        f_space: Space frequency in Hz (bit 0, default 2100 per M.493)
        f_mark: Mark frequency in Hz (bit 1, default 1300 per M.493)

    Returns:
        Binary bitstream as numpy array of 0s and 1s
    """
    samples_per_bit = sample_rate / baud_rate
    num_bits = int(len(samples) / samples_per_bit)

    bitstream = np.zeros(num_bits, dtype=np.uint8)

    for i in range(num_bits):
        start_idx = int(i * samples_per_bit)
        end_idx = int((i + 1) * samples_per_bit)

        # Extract window for this bit
        window = samples[start_idx:end_idx]

        # Calculate power at both frequencies
        power_space = goertzel_filter(window, f_space, sample_rate)
        power_mark = goertzel_filter(window, f_mark, sample_rate)

        # Determine bit value
        # Mark (2100 Hz) = 1, Space (1300 Hz) = 0
        bitstream[i] = 1 if power_mark > power_space else 0

    return bitstream


def demodulate_bandpass(samples: np.ndarray, sample_rate: int,
                        baud_rate: int = 1200,
                        f_space: float = 2100.0,
                        f_mark: float = 1300.0) -> np.ndarray:
    """
    Demodulate FSK signal using bandpass filters (fallback method).

    Args:
        samples: Audio samples (mono, float32, normalized)
        sample_rate: Sample rate in Hz
        baud_rate: Symbol rate in baud (default 1200)
        f_space: Space frequency in Hz (bit 0, default 2100 per M.493)
        f_mark: Mark frequency in Hz (bit 1, default 1300 per M.493)

    Returns:
        Binary bitstream as numpy array of 0s and 1s
    """

    def bandpass_filter(data, lowcut, highcut, fs, order=5):
        """Create and apply bandpass filter using Butterworth."""
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        sos = butter(order, [low, high], btype='band', output='sos')
        return sosfilt(sos, data)

    # Filter around each frequency (±50 Hz bandwidth)
    filtered_space = bandpass_filter(samples, f_space - 50, f_space + 50, sample_rate)
    filtered_mark = bandpass_filter(samples, f_mark - 50, f_mark + 50, sample_rate)

    # Get amplitude envelopes
    amplitude_space = np.abs(filtered_space)
    amplitude_mark = np.abs(filtered_mark)

    # Sample at bit rate
    samples_per_bit = sample_rate / baud_rate
    num_bits = int(len(samples) / samples_per_bit)

    bitstream = np.zeros(num_bits, dtype=np.uint8)

    for i in range(num_bits):
        start_idx = int(i * samples_per_bit)
        end_idx = int((i + 1) * samples_per_bit)

        # Average amplitude in this bit period
        avg_amp_space = np.mean(amplitude_space[start_idx:end_idx])
        avg_amp_mark = np.mean(amplitude_mark[start_idx:end_idx])

        # Determine bit value
        bitstream[i] = 1 if avg_amp_mark > avg_amp_space else 0

    return bitstream


class FSKDemodulator:
    """
    FSK demodulator with multiple strategies.

    Supports both Goertzel algorithm and bandpass filtering methods.
    """

    def __init__(self, method: str = 'goertzel', baud_rate: int = 1200,
                 f_space: float = 2100.0, f_mark: float = 1300.0):
        """
        Initialize FSK demodulator.

        Args:
            method: Demodulation method ('goertzel' or 'bandpass')
            baud_rate: Symbol rate in baud (default 1200)
            f_space: Space frequency in Hz (default 2100 per M.493)
            f_mark: Mark frequency in Hz (default 1300 per M.493)
        """
        self.method = method
        self.baud_rate = baud_rate
        self.f_space = f_space
        self.f_mark = f_mark

    def demodulate(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Demodulate FSK signal to binary bitstream.

        Args:
            samples: Audio samples (mono, normalized)
            sample_rate: Sample rate in Hz

        Returns:
            Binary bitstream as numpy array of 0s and 1s
        """
        if self.method == 'goertzel':
            return demodulate_goertzel(
                samples, sample_rate, self.baud_rate,
                self.f_space, self.f_mark
            )
        elif self.method == 'bandpass':
            return demodulate_bandpass(
                samples, sample_rate, self.baud_rate,
                self.f_space, self.f_mark
            )
        else:
            raise ValueError(f"Unknown demodulation method: {self.method}")

    def get_signal_strength(self, samples: np.ndarray, sample_rate: int) -> dict:
        """
        Get signal strength at mark and space frequencies.

        Useful for debugging and signal quality assessment.

        Args:
            samples: Audio samples
            sample_rate: Sample rate in Hz

        Returns:
            Dictionary with 'space' and 'mark' power levels
        """
        power_space = goertzel_filter(samples, self.f_space, sample_rate)
        power_mark = goertzel_filter(samples, self.f_mark, sample_rate)

        return {
            'space': power_space,
            'mark': power_mark,
            'snr_db': 10 * np.log10(max(power_mark, power_space) /
                                   (min(power_mark, power_space) + 1e-10))
        }

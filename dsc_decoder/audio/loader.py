"""
Audio file loader for DSC decoder.

Supports WAV, MP3, OGG, FLAC and converts to mono at 22050 Hz sample rate.
"""

import numpy as np
from pathlib import Path
from typing import Tuple


def load_audio(file_path: str, target_sr: int = 22050) -> Tuple[np.ndarray, int]:
    """
    Load audio file and preprocess for DSC decoding.

    Handles multiple formats (WAV, MP3, OGG, FLAC) and converts to:
    - Mono (average of channels if stereo)
    - Target sample rate (default 22050 Hz, optimal for 1200 baud)
    - Normalized float32 array

    Args:
        file_path: Path to audio file
        target_sr: Target sample rate in Hz (default 22050)

    Returns:
        Tuple of (samples, sample_rate) where samples is a 1D numpy array

    Raises:
        FileNotFoundError: If audio file doesn't exist
        ValueError: If audio file format is not supported or invalid
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    # Try librosa first (supports all formats)
    try:
        import librosa
        import soundfile as sf

        # Load audio with librosa
        samples, sample_rate = librosa.load(
            str(file_path),
            sr=target_sr,  # Resample to target
            mono=True      # Convert to mono
        )

        # Normalize to [-1, 1] range
        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        max_val = np.abs(samples).max()
        if max_val > 0:
            samples = samples / max_val

        return samples, sample_rate

    except ImportError:
        # Fallback to scipy for WAV files only
        if file_path.suffix.lower() not in ['.wav', '.wave']:
            raise ValueError(
                f"librosa is not installed. Only WAV files are supported without librosa. "
                f"Install with: pip install librosa\n"
                f"File format: {file_path.suffix}"
            )

        from scipy.io import wavfile
        from scipy.signal import resample

        # Load WAV file
        original_sr, data = wavfile.read(str(file_path))

        # Convert to float32
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128) / 128.0
        else:
            data = data.astype(np.float32)

        # Convert stereo to mono
        if len(data.shape) > 1:
            data = data.mean(axis=1)

        # Resample if needed
        if original_sr != target_sr:
            num_samples = int(len(data) * target_sr / original_sr)
            data = resample(data, num_samples)

        # Normalize
        max_val = np.abs(data).max()
        if max_val > 0:
            data = data / max_val

        return data, target_sr


def get_audio_info(file_path: str) -> dict:
    """
    Get information about an audio file without loading it completely.

    Args:
        file_path: Path to audio file

    Returns:
        Dictionary with keys: 'duration', 'sample_rate', 'channels', 'format'
    """
    file_path = Path(file_path)

    try:
        import librosa
        import soundfile as sf

        info = sf.info(str(file_path))

        return {
            'duration': info.duration,
            'sample_rate': info.samplerate,
            'channels': info.channels,
            'format': info.format,
            'subtype': info.subtype
        }
    except ImportError:
        # Fallback for WAV files
        from scipy.io import wavfile

        sample_rate, data = wavfile.read(str(file_path))
        duration = len(data) / sample_rate
        channels = 1 if len(data.shape) == 1 else data.shape[1]

        return {
            'duration': duration,
            'sample_rate': sample_rate,
            'channels': channels,
            'format': 'WAV'
        }

import os
import tempfile
import unittest
import wave

import numpy as np

from stress_scorer import StressResult, score_stress


def write_temp_wav(samples: np.ndarray, sr: int = 16000) -> str:
    samples = np.asarray(samples, dtype=np.float32)
    clipped = np.clip(samples, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())

    return path


class StressScorerTests(unittest.TestCase):
    def test_silent_audio_low_stress(self):
        sr = 16000
        samples = np.zeros(sr, dtype=np.float32)  # 1 second silence
        path = write_temp_wav(samples, sr)
        try:
            result = score_stress(path)
            self.assertEqual(result.alert_level, "LOW")
            self.assertGreaterEqual(result.stress_score, 0)
            self.assertLessEqual(result.stress_score, 100)
        finally:
            os.remove(path)

    def test_noisy_audio_has_nonzero_score(self):
        rng = np.random.default_rng(42)
        sr = 16000
        samples = rng.normal(0, 0.3, sr * 2).astype(np.float32)  # 2 seconds noise
        path = write_temp_wav(samples, sr)
        try:
            result = score_stress(path)
            self.assertGreater(result.stress_score, 0)
        finally:
            os.remove(path)

    def test_score_always_in_range(self):
        rng = np.random.default_rng(7)
        sr = 16000
        cases = [
            np.zeros(sr, dtype=np.float32),
            rng.normal(0, 0.1, sr).astype(np.float32),
            np.sin(2 * np.pi * 220 * np.arange(sr) / sr).astype(np.float32),
            np.zeros(int(sr * 0.2), dtype=np.float32),  # short file
        ]
        paths = [write_temp_wav(samples, sr) for samples in cases]

        try:
            for path in paths:
                result = score_stress(path)
                self.assertGreaterEqual(result.stress_score, 0)
                self.assertLessEqual(result.stress_score, 100)
        finally:
            for path in paths:
                os.remove(path)

    def test_stress_result_fields_present(self):
        sr = 16000
        samples = np.zeros(sr, dtype=np.float32)
        path = write_temp_wav(samples, sr)
        try:
            result = score_stress(path)
            self.assertIsInstance(result, StressResult)
            for field in [
                "timestamp",
                "audio_path",
                "duration_s",
                "stress_score",
                "alert_level",
                "indicators",
                "features",
            ]:
                self.assertTrue(hasattr(result, field), field)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()

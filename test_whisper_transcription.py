import sys
import types
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Keep tests isolated from optional audio runtime dependencies.
if "soundfile" not in sys.modules:
    soundfile_stub = types.ModuleType("soundfile")
    soundfile_stub.write = lambda *args, **kwargs: None
    sys.modules["soundfile"] = soundfile_stub

if "scipy" not in sys.modules:
    import scipy as _real_scipy  # ensure real scipy is loaded first
if not hasattr(sys.modules.get("scipy", types.SimpleNamespace()), "signal") or not hasattr(
    getattr(sys.modules.get("scipy", None), "signal", None), "resample_poly"
):
    # Only stub if real scipy.signal.resample_poly is unavailable
    try:
        from scipy.signal import resample_poly as _rp  # noqa: F401
    except ImportError:
        scipy_stub = types.ModuleType("scipy")
        scipy_stub.signal = types.SimpleNamespace(resample_poly=None)
        sys.modules.setdefault("scipy", scipy_stub)

import autonomous_voice_hunter
from whisper_transcription import WhisperConfig, transcribe_audio, transcribe_audio_file


def _write_test_wav(path: Path, sample_rate: int = 16000, duration_sec: float = 0.2) -> None:
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    signal = (0.3 * np.sin(2.0 * np.pi * 440.0 * t) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(signal.tobytes())


def test_transcribe_audio_file_uses_faster_whisper(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "sample.wav"
    _write_test_wav(audio_path)

    class DummySegment:
        def __init__(self, start: float, end: float, text: str) -> None:
            self.start = start
            self.end = end
            self.text = text

    class DummyInfo:
        language = "en"
        language_probability = 0.99
        duration = 1.2

    class DummyModel:
        def __init__(self, model_size: str, device: str, compute_type: str) -> None:
            assert model_size == "large-v3"
            assert device == "auto"
            assert compute_type == "default"

        def transcribe(self, audio_file: str, beam_size: int, vad_filter: bool, language=None):
            assert audio_file.endswith("sample.wav")
            assert beam_size == 5
            assert vad_filter is True
            assert language is None
            return iter(
                [
                    DummySegment(0.0, 0.5, " hello "),
                    DummySegment(0.5, 1.0, "world"),
                ]
            ), DummyInfo()

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=DummyModel),
    )

    result = transcribe_audio_file(audio_path, WhisperConfig())

    assert result["text"] == "hello world"
    assert result["language"] == "en"
    assert len(result["segments"]) == 2
    assert result["segments"][0]["text"] == "hello"


def test_transcribe_audio_returns_text_only(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "sample.wav"
    _write_test_wav(audio_path)

    monkeypatch.setattr(
        "whisper_transcription.transcribe_audio_file",
        lambda path, config=None: {
            "text": "  distress message  ",
            "language": "en",
            "segments": [{"start": 0.0, "end": 0.5, "text": "distress message"}],
        },
    )

    text = transcribe_audio(audio_path)

    assert text == "distress message"


def test_autonomous_hunter_auto_transcribe_writes_artifacts(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    hunter = autonomous_voice_hunter.AutonomousVoiceHunter(session_name="test-session")

    audio_path = hunter.session_dir / "capture.wav"
    _write_test_wav(audio_path)

    def fake_transcribe(path, config):
        assert str(path).endswith("capture.wav")
        assert config.model_size == "large-v3"
        return {
            "text": "distress call from vessel",
            "segments": [{"start": 0.0, "end": 1.0, "text": "distress call from vessel"}],
            "language": "en",
        }

    monkeypatch.setattr(autonomous_voice_hunter, "transcribe_audio_file", fake_transcribe)

    result = hunter._auto_transcribe_capture(audio_path, "CH16", 156_800_000.0)

    assert result["text"] == "distress call from vessel"
    assert len(hunter.transcriptions) == 1
    assert (hunter.transcripts_dir / "capture.txt").exists()
    assert (hunter.transcripts_dir / "capture.json").exists()


def test_transcribe_audio_file_probes_priority_languages_when_auto_is_uncertain(
    monkeypatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "sample.wav"
    _write_test_wav(audio_path)

    calls = []
    scores = {
        None: -1.8,
        "mt": -1.4,
        "ar": -0.2,
        "it": -0.6,
        "en": -0.8,
    }

    class DummySegment:
        def __init__(self, text: str, score: float) -> None:
            self.start = 0.0
            self.end = 0.5
            self.text = text
            self.avg_logprob = score

    class DummyInfo:
        def __init__(self, language: str, language_probability: float) -> None:
            self.language = language
            self.language_probability = language_probability
            self.duration = 0.5

    class DummyModel:
        def __init__(self, model_size: str, device: str, compute_type: str) -> None:
            assert model_size == "large-v3"
            assert device == "auto"
            assert compute_type == "default"

        def transcribe(self, audio_file: str, beam_size: int, vad_filter: bool, language=None):
            calls.append(language)
            score = scores[language]
            if language is None:
                info = DummyInfo(language="de", language_probability=0.31)
                segment = DummySegment("auto result", score)
            else:
                info = DummyInfo(language=language, language_probability=0.95)
                segment = DummySegment(f"{language} result", score)
            return iter([segment]), info

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=DummyModel),
    )

    result = transcribe_audio_file(audio_path, WhisperConfig())

    assert calls == [None, "mt", "ar", "it", "en"]
    assert result["language"] == "ar"
    assert result["text"] == "ar result"


def test_extended_capture_discards_noise_only_samples_before_write(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NOISE_GATE_DB", "-20")
    hunter = autonomous_voice_hunter.AutonomousVoiceHunter(session_name="test-session")

    low_energy_audio = np.full(48_000, 0.01, dtype=np.float32)
    monkeypatch.setattr(
        hunter,
        "create_rf_sample",
        lambda frequency_hz, duration: (low_energy_audio, True),
    )

    write_calls = []
    monkeypatch.setattr(
        autonomous_voice_hunter.sf,
        "write",
        lambda *args, **kwargs: write_calls.append((args, kwargs)),
    )

    monitor_calls = []
    monkeypatch.setattr(
        hunter,
        "monitor_for_continued_activity",
        lambda *args, **kwargs: monitor_calls.append((args, kwargs)) or 0,
    )

    capture_path, capture_duration = hunter.extended_voice_capture(
        "CH16", 156_800_000.0, datetime.now(timezone.utc)
    )

    assert hunter.noise_gate_db == -20.0
    assert capture_path is None
    assert capture_duration == 0
    assert write_calls == []


def test_monitor_for_continued_activity_accepts_full_voice_detection_tuple(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    hunter = autonomous_voice_hunter.AutonomousVoiceHunter(session_name="test-session")

    silent = np.zeros(48_000, dtype=np.float32)
    monkeypatch.setattr(hunter, "create_rf_sample", lambda frequency_hz, duration: (silent, False))
    monkeypatch.setattr(
        hunter,
        "detect_voice_activity",
        lambda audio, sample_rate, frequency_hz=None: (
            False,
            0.0,
            0.0,
            hunter._voice_ratio_threshold_for_frequency(frequency_hz),
        ),
    )
    monkeypatch.setattr(autonomous_voice_hunter.time, "sleep", lambda *_args, **_kwargs: None)

    monitored = hunter.monitor_for_continued_activity("CH16", 156_800_000.0)
    assert monitored == 30
    assert hunter.stats["captures_saved"] == 0
    assert hunter.voice_captures == []


def test_transcribe_audio_file_supports_openai_whisper_backend(
    monkeypatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "sample.wav"
    _write_test_wav(audio_path)

    class DummyModel:
        def transcribe(
            self,
            audio_file: str,
            language=None,
            beam_size: int = 5,
            fp16: bool = False,
            verbose: bool = False,
        ):
            assert audio_file.endswith("sample.wav")
            assert language is None
            assert beam_size == 5
            assert fp16 is False
            assert verbose is False
            return {
                "text": "hello from openai whisper",
                "language": "en",
                "segments": [
                    {"start": 0.0, "end": 0.6, "text": "hello", "avg_logprob": -0.2},
                    {"start": 0.6, "end": 1.0, "text": "from openai whisper", "avg_logprob": -0.3},
                ],
            }

    def fake_load_model(model_size: str):
        assert model_size == "large-v3"
        return DummyModel()

    monkeypatch.setitem(sys.modules, "whisper", types.SimpleNamespace(load_model=fake_load_model))

    result = transcribe_audio_file(audio_path, WhisperConfig(backend="openai-whisper"))

    assert result["text"] == "hello from openai whisper"
    assert result["language"] == "en"
    assert result["backend"] == "openai-whisper"
    assert len(result["segments"]) == 2

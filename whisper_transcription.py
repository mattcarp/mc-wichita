#!/usr/bin/env python3
"""
Whisper transcription helpers for Wichita RF captures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

PRIORITY_LANGUAGES = ("mt", "ar", "it", "en")


@dataclass
class WhisperConfig:
    model_size: str = "large-v3"
    device: str = "auto"
    compute_type: str = "default"
    backend: str = "auto"
    beam_size: int = 5
    vad_filter: bool = True
    language: Optional[str] = None
    language_priority: List[str] = field(
        default_factory=lambda: list(PRIORITY_LANGUAGES)
    )


class WhisperDependencyError(RuntimeError):
    """Raised when no supported Whisper backend is available."""


def transcribe_audio_file(
    audio_file_path: str | Path,
    config: Optional[WhisperConfig] = None,
) -> Dict[str, Any]:
    """
    Transcribe an audio file with faster-whisper and return structured output.
    """
    cfg = config or WhisperConfig()
    path = Path(audio_file_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    backend = cfg.backend.strip().lower() if isinstance(cfg.backend, str) else "auto"
    if backend not in {"auto", "faster-whisper", "openai-whisper"}:
        raise ValueError(
            f"Unsupported whisper backend '{cfg.backend}'. "
            "Use one of: auto, faster-whisper, openai-whisper"
        )

    def _make_faster_runner():
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return None

        model = WhisperModel(
            cfg.model_size,
            device=cfg.device,
            compute_type=cfg.compute_type,
        )

        def _run(language_hint: Optional[str]) -> Dict[str, Any]:
            segments_iter, info = model.transcribe(
                str(path),
                beam_size=cfg.beam_size,
                vad_filter=cfg.vad_filter,
                language=language_hint,
            )
            raw_segments = list(segments_iter)
            return {
                "backend": "faster-whisper",
                "raw_segments": raw_segments,
                "language": _normalized(getattr(info, "language", None)) or language_hint,
                "language_probability": getattr(info, "language_probability", None),
                "duration": getattr(info, "duration", None),
            }

        return _run

    def _make_openai_runner():
        try:
            import whisper
        except ImportError:
            return None

        model = whisper.load_model(cfg.model_size)

        def _run(language_hint: Optional[str]) -> Dict[str, Any]:
            result = model.transcribe(
                str(path),
                language=language_hint,
                beam_size=cfg.beam_size,
                fp16=False,
                verbose=False,
            )
            raw_segments = list(result.get("segments", []))
            return {
                "backend": "openai-whisper",
                "raw_segments": raw_segments,
                "language": _normalized(result.get("language")) or language_hint,
                "language_probability": None,
                "duration": None,
                "text": result.get("text", ""),
            }

        return _run

    runner = None
    if backend == "faster-whisper":
        runner = _make_faster_runner()
    elif backend == "openai-whisper":
        runner = _make_openai_runner()
    else:
        runner = _make_faster_runner() or _make_openai_runner()

    if runner is None:
        raise WhisperDependencyError(
            "No Whisper backend is installed. Install with: "
            "pip install faster-whisper or pip install openai-whisper"
        )

    def _normalized(code: Optional[str]) -> Optional[str]:
        if not code or not isinstance(code, str):
            return None
        return code.strip().lower() or None

    priority = []
    for code in cfg.language_priority:
        normalized = _normalized(code)
        if normalized and normalized not in priority:
            priority.append(normalized)

    def _run_transcription(language_hint: Optional[str]) -> Dict[str, Any]:
        transcription = runner(language_hint)
        raw_segments = transcription.get("raw_segments", [])

        segment_list: List[Dict[str, Any]] = []
        text_chunks: List[str] = []
        confidence_scores: List[float] = []

        for segment in raw_segments:
            if isinstance(segment, dict):
                seg_text = str(segment.get("text", "")).strip()
                seg_start = float(segment.get("start", 0.0))
                seg_end = float(segment.get("end", seg_start))
                avg_logprob = segment.get("avg_logprob")
            else:
                seg_text = str(getattr(segment, "text", "")).strip()
                seg_start = float(getattr(segment, "start", 0.0))
                seg_end = float(getattr(segment, "end", seg_start))
                avg_logprob = getattr(segment, "avg_logprob", None)
            if not seg_text:
                continue
            segment_list.append(
                {
                    "start": seg_start,
                    "end": seg_end,
                    "text": seg_text,
                }
            )
            text_chunks.append(seg_text)

            if isinstance(avg_logprob, (int, float)):
                confidence_scores.append(float(avg_logprob))

        score = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else float("-inf")
        )

        return {
            "text": (" ".join(text_chunks).strip() or str(transcription.get("text", "")).strip()),
            "segments": segment_list,
            "language": _normalized(transcription.get("language")) or language_hint,
            "language_probability": transcription.get("language_probability"),
            "duration": transcription.get("duration"),
            "model": cfg.model_size,
            "backend": transcription.get("backend"),
            "_score": score,
            "_requested_language": language_hint,
        }

    if cfg.language:
        result = _run_transcription(_normalized(cfg.language))
    else:
        auto_result = _run_transcription(None)
        result = auto_result
        auto_language = _normalized(auto_result.get("language"))
        auto_prob = auto_result.get("language_probability")
        auto_prob = float(auto_prob) if isinstance(auto_prob, (int, float)) else 0.0

        # openai-whisper doesn't expose language_probability; skip probing to
        # avoid calling model.transcribe() with a forced language_hint when the
        # caller has not set cfg.language.
        should_probe_priority = (
            bool(priority)
            and backend != "openai-whisper"
            and (auto_language not in priority or auto_prob < 0.80)
        )

        if should_probe_priority:
            candidates = [auto_result]
            for language_code in priority:
                candidates.append(_run_transcription(language_code))

            def _candidate_rank(candidate: Dict[str, Any]) -> tuple[float, float]:
                score = float(candidate.get("_score", float("-inf")))
                language_code = _normalized(
                    candidate.get("language") or candidate.get("_requested_language")
                )
                if language_code in priority:
                    # Small deterministic preference by requested language priority.
                    # Higher priority => slightly higher rank when confidence is close.
                    idx = priority.index(language_code)
                    priority_bonus = (len(priority) - idx) * 0.001
                else:
                    priority_bonus = 0.0
                return (score + priority_bonus, -len(candidate.get("text", "")))

            result = max(candidates, key=_candidate_rank)

    result.pop("_score", None)
    result.pop("_requested_language", None)
    return result


def transcribe_audio(
    filepath: str | Path,
    config: Optional[WhisperConfig] = None,
) -> str:
    """
    Convenience wrapper that returns transcription text only.
    """
    result = transcribe_audio_file(filepath, config)
    return str(result.get("text", "")).strip()


__all__ = [
    "PRIORITY_LANGUAGES",
    "WhisperConfig",
    "WhisperDependencyError",
    "transcribe_audio_file",
    "transcribe_audio",
]

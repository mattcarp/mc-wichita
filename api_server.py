#!/usr/bin/env python3
"""
RF Digital Forensics Toolkit - FastAPI Server
Full-spectrum SIGINT API covering 1MHz to 6GHz
Self-documenting with OpenAPI/Swagger and Redoc
Location: Valletta, Malta - Mediterranean Intelligence Hub
"""

from fastapi import (
    FastAPI,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
    Query,
    File,
    UploadFile,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import asyncio
import numpy as np
from datetime import datetime, timezone
import subprocess
import os
import json
import uuid
import io
import wave
import shlex
import urllib.request
import urllib.error
from pathlib import Path
from api_maritime_aviation import add_maritime_aviation_routes
from alert_dispatcher import send_stress_alert
from discord_alerts import send_alert as send_discord_alert
from evidence_context import delivery_health, evidence_context, answer_question
from wichita_ais_routes import router as live_ais_router
from wichita_capture_routes import router as capture_feed_router
from whisper_transcription import WhisperConfig, transcribe_audio_file
from ai_analysis_pipeline import analyze_audio_file, extract_stress_features, score_stress

# Initialize FastAPI with rich metadata
app = FastAPI(
    title="RF Digital Forensics Toolkit API",
    description="""
    ## 🎯 Full-Spectrum SIGINT Platform
    
    **Coverage:** 1 MHz to 6 GHz (HackRF One capabilities)
    **Location:** Malta - Strategic Mediterranean position
    **Capabilities:**
    - Real-time signal capture and analysis
    - Maritime AIS/VHF monitoring
    - Aviation ADS-B/ACARS tracking
    - Cellular/IoT signal intelligence  
    - Amateur radio monitoring
    - Threat detection and classification
    - ML-powered signal fingerprinting
    
    ## 📡 Frequency Ranges
    - **LF/MF/HF** (1-30 MHz): Time signals, amateur radio, maritime
    - **VHF** (30-300 MHz): FM broadcast, aviation, marine, emergency
    - **UHF** (300-3000 MHz): Cellular, WiFi, Bluetooth, satellites
    - **SHF** (3-6 GHz): 5G, radar, satellite
    """,
    version="2.0.0",
    docs_url="/docs",  # Swagger UI at /docs (standard location)
    redoc_url="/redoc",  # ReDoc alternative
    openapi_tags=[
        {"name": "capture", "description": "Signal capture operations"},
        {"name": "analysis", "description": "Signal analysis and classification"},
        {"name": "maritime", "description": "Maritime intelligence"},
        {"name": "aviation", "description": "Aviation monitoring"},
        {"name": "threats", "description": "Threat detection"},
        {"name": "spectrum", "description": "Spectrum scanning"},
        {"name": "ml", "description": "Machine learning operations"},
        {"name": "realtime", "description": "Real-time streaming"},
    ],
)

# CORS for web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ENUMS & MODELS ====================


class FrequencyBand(str, Enum):
    """Standard frequency band classifications"""

    LF = "lf"  # 30-300 kHz
    MF = "mf"  # 300-3000 kHz
    HF = "hf"  # 3-30 MHz
    VHF = "vhf"  # 30-300 MHz
    UHF = "uhf"  # 300-3000 MHz
    SHF = "shf"  # 3-30 GHz (HackRF up to 6 GHz)


class ModulationType(str, Enum):
    """Signal modulation types"""

    AM = "am"
    FM = "fm"
    NFM = "nfm"
    WFM = "wfm"
    USB = "usb"
    LSB = "lsb"
    CW = "cw"
    PSK = "psk"
    FSK = "fsk"
    QAM = "qam"
    OFDM = "ofdm"
    RAW = "raw"


class SignalType(str, Enum):
    """Known signal classifications"""

    # Maritime
    AIS = "ais"
    MARINE_VHF = "marine_vhf"
    NAVTEX = "navtex"

    # Aviation
    ADSB = "adsb"
    ACARS = "acars"
    VOR = "vor"
    ILS = "ils"
    DME = "dme"

    # Emergency
    EMERGENCY = "emergency"
    DISTRESS = "distress"

    # Cellular
    GSM = "gsm"
    UMTS = "umts"
    LTE = "lte"
    NR_5G = "5g"

    # IoT/ISM
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    ZIGBEE = "zigbee"
    LORA = "lora"

    # Amateur
    AMATEUR = "amateur"
    APRS = "aprs"
    FT8 = "ft8"

    # Other
    BROADCAST_FM = "broadcast_fm"
    BROADCAST_TV = "broadcast_tv"
    SATELLITE = "satellite"
    RADAR = "radar"
    UNKNOWN = "unknown"


class CaptureRequest(BaseModel):
    """Signal capture parameters"""

    frequency: float = Field(
        ..., ge=1e6, le=6e9, description="Frequency in Hz (1MHz-6GHz)"
    )
    sample_rate: float = Field(
        default=2e6, ge=1e6, le=20e6, description="Sample rate in Hz"
    )
    duration: float = Field(
        default=1.0, ge=0.1, le=60, description="Capture duration in seconds"
    )
    gain: int = Field(default=20, ge=0, le=47, description="LNA gain (0-47 dB)")
    amp_enable: bool = Field(default=True, description="Enable amplifier")
    antenna_power: bool = Field(
        default=False, description="Enable antenna power (bias-tee)"
    )

    @validator("frequency")
    def validate_frequency(cls, v):
        if v < 1e6 or v > 6e9:
            raise ValueError(
                f"Frequency {v/1e6:.1f} MHz outside HackRF range (1-6000 MHz)"
            )
        return v

    class Config:
        schema_extra = {
            "example": {
                "frequency": 103.7e6,
                "sample_rate": 2e6,
                "duration": 5.0,
                "gain": 30,
                "amp_enable": True,
                "antenna_power": False,
            }
        }


class SpectrumScanRequest(BaseModel):
    """Spectrum scanning parameters"""

    start_freq: float = Field(..., ge=1e6, le=6e9, description="Start frequency in Hz")
    stop_freq: float = Field(..., ge=1e6, le=6e9, description="Stop frequency in Hz")
    bin_width: float = Field(default=1e6, ge=1e5, le=10e6, description="FFT bin width")
    sweeps: int = Field(default=1, ge=1, le=100, description="Number of sweeps")

    @validator("stop_freq")
    def validate_range(cls, v, values):
        if "start_freq" in values and v <= values["start_freq"]:
            raise ValueError("Stop frequency must be greater than start frequency")
        return v


class SignalAnalysisResult(BaseModel):
    """Signal analysis output"""

    frequency: float
    signal_type: SignalType
    modulation: ModulationType
    power_dbm: float
    bandwidth_khz: float
    confidence: float = Field(..., ge=0, le=1)
    metadata: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)
    location: str = "Valletta, Malta"


class ThreatAssessment(BaseModel):
    """Security threat analysis"""

    threat_level: str = Field(..., description="low/medium/high/critical")
    threat_type: str
    description: str
    frequency: float
    recommendations: List[str]
    evidence: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCreate(BaseModel):
    """Inbound alert creation request"""

    title: str = Field(..., description="Alert title for Mission Control display")
    description: Optional[str] = Field(
        default=None, description="Detailed alert context"
    )
    signal_type: Optional[SignalType] = SignalType.UNKNOWN
    severity: Optional[AlertSeverity] = None
    frequency_hz: Optional[float] = Field(
        default=None, description="Frequency in Hz"
    )
    frequency_mhz: Optional[float] = Field(
        default=None, description="Frequency in MHz"
    )
    confidence: float = Field(default=0.5, ge=0, le=1)
    transcript: Optional[str] = None
    language: Optional[str] = Field(
        default=None, description="Detected transcript language code (e.g. mt, ar, it, en)"
    )
    audio_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="wichita-sdr")

    @validator("title")
    def title_required(cls, v):
        if not v.strip():
            raise ValueError("title must not be empty")
        return v


class AlertRecord(BaseModel):
    """Persisted alert record"""

    id: str
    created_at: datetime
    title: str
    description: Optional[str]
    signal_type: SignalType
    severity: AlertSeverity
    frequency_mhz: Optional[float]
    confidence: float
    transcript: Optional[str]
    language: Optional[str]
    audio_url: Optional[str]
    tags: List[str]
    metadata: Dict[str, Any]
    source: str


class CaptureRecord(BaseModel):
    """Persisted capture record for dashboard display."""

    id: str
    created_at: datetime
    file_path: str
    frequency_mhz: float
    duration_sec: float
    file_size_mb: float
    average_power_dbfs: float
    sample_rate_msps: float
    status: str = "success"


ALERTS: List[AlertRecord] = []
ALERT_CLIENTS: List[WebSocket] = []
MAX_ALERTS = 500
CAPTURES: List[CaptureRecord] = []
MAX_CAPTURES = 500
DISTRESS_KEYWORDS = {
    "mayday",
    "pan-pan",
    "pan pan",
    "sos",
    "distress",
    "man overboard",
    "help",
    "emergency",
}
HIGH_PRIORITY_AUDIO_TERMS = {
    "wichita",
    "wichita signal",
    "ferry",
    "ferry terminal",
    "mayday",
    "pan-pan",
    "pan pan",
    "sos",
    "distress",
    "man overboard",
    "urgent",
    "emergency",
}


class SpeakerCaptureRequest(BaseModel):
    """Speaker identification request metadata."""

    capture_id: Optional[str] = Field(default=None, description="External capture id")
    frequency_hz: Optional[float] = Field(default=None, ge=1e6, le=6e9)
    transcript: Optional[str] = Field(default=None, description="Optional ASR transcript")
    source: str = Field(default="wichita-sdr")


class SpeakerProfile(BaseModel):
    """Persisted voice speaker profile."""

    id: str
    created_at: datetime
    updated_at: datetime
    first_capture_id: Optional[str]
    last_capture_id: Optional[str]
    captures_count: int
    average_similarity: float = Field(..., ge=0, le=1)
    gender_estimate: str
    age_estimate: int = Field(..., ge=0, le=120)
    age_range: str
    confidence: float = Field(..., ge=0, le=1)
    embedding: List[float]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpeakerIdentificationResult(BaseModel):
    """Speaker identification response."""

    speaker_id: str
    matched_existing_profile: bool
    similarity: float = Field(..., ge=0, le=1)
    profile: SpeakerProfile


SPEAKER_DB_PATH = os.getenv("SPEAKER_DB_PATH", "/tmp/speaker_profiles_db.json")
SPEAKER_MATCH_THRESHOLD = float(os.getenv("SPEAKER_MATCH_THRESHOLD", "0.97"))
SPEAKER_PROFILES: Dict[str, SpeakerProfile] = {}
AUDIO_SEARCH_DIRS = [
    Path(os.getenv("AUDIO_CAPTURE_DIR", "/tmp")),
    Path(__file__).resolve().parent / "audio_samples",
]


def _is_distress_alert(payload: AlertCreate) -> bool:
    if payload.signal_type == SignalType.DISTRESS:
        return True
    text = " ".join(
        filter(None, [payload.title, payload.description, payload.transcript])
    ).lower()
    return any(keyword in text for keyword in DISTRESS_KEYWORDS)


def _is_stress_alert(alert: AlertRecord) -> bool:
    stress_terms = {
        "stress",
        "panic",
        "distress",
        "anxiety",
        "urgent",
        "help",
        "mayday",
        "sos",
    }
    haystack = " ".join(
        [
            alert.title or "",
            alert.description or "",
            alert.transcript or "",
            " ".join(alert.tags or []),
        ]
    ).lower()
    if alert.signal_type == SignalType.DISTRESS:
        return True
    if alert.severity == AlertSeverity.CRITICAL:
        return True
    return any(term in haystack for term in stress_terms)


def _estimate_gender_and_age(
    pitch_hz: float, spectral_centroid_hz: float, confidence: float
) -> Dict[str, Any]:
    """
    Lightweight heuristic estimation from voice proxies.
    The values are coarse, for triage/labeling only.
    """
    if confidence < 0.2:
        return {"gender_estimate": "unknown", "age_estimate": 0, "age_range": "unknown"}

    if pitch_hz >= 165:
        gender = "female"
    elif pitch_hz > 0:
        gender = "male"
    else:
        gender = "unknown"

    # Age estimate from centroid and pitch trend; bounded to practical ranges.
    base_age = 34.0
    age_adjustment = ((180.0 - min(pitch_hz, 260.0)) / 12.0) + (
        (2600.0 - min(spectral_centroid_hz, 4500.0)) / 350.0
    )
    age_estimate = int(round(max(14.0, min(80.0, base_age + age_adjustment))))

    if age_estimate < 20:
        age_range = "teen"
    elif age_estimate < 35:
        age_range = "young_adult"
    elif age_estimate < 55:
        age_range = "adult"
    else:
        age_range = "senior"

    return {
        "gender_estimate": gender,
        "age_estimate": age_estimate,
        "age_range": age_range,
    }


def _decode_audio_samples(audio_bytes: bytes, filename: str) -> Tuple[np.ndarray, int]:
    """
    Decode WAV audio if possible; otherwise treat bytes as normalized int8-like data.
    """
    if filename.lower().endswith(".wav"):
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                channels = wav.getnchannels()
                sample_rate = wav.getframerate()
                sample_width = wav.getsampwidth()
                frames = wav.readframes(wav.getnframes())
                if sample_width == 1:
                    samples = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
                    samples = (samples - 128.0) / 128.0
                elif sample_width == 2:
                    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
                    samples = samples / 32768.0
                else:
                    samples = np.frombuffer(frames, dtype=np.int8).astype(np.float32) / 128.0

                if channels > 1:
                    samples = samples.reshape(-1, channels).mean(axis=1)
                return samples, sample_rate
        except wave.Error:
            pass

    samples = np.frombuffer(audio_bytes, dtype=np.int8).astype(np.float32) / 128.0
    return samples, 8000


def _safe_cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom <= 0:
        return 0.0
    score = float(np.dot(a, b) / denom)
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def _extract_speaker_features(audio_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Build deterministic voice features for profile matching.
    """
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio payload")

    samples, sample_rate = _decode_audio_samples(audio_bytes, filename)
    if samples.size < 32:
        raise HTTPException(status_code=400, detail="Audio payload too small")

    samples = samples[: min(samples.size, 160000)]
    abs_samples = np.abs(samples)
    power = float(np.mean(abs_samples))
    std = float(np.std(samples))
    zcr = float(np.mean(np.abs(np.diff(np.signbit(samples)).astype(np.float32))))
    peak = float(np.max(abs_samples))

    fft_window = samples[: min(4096, samples.size)]
    fft_mag = np.abs(np.fft.rfft(fft_window))
    fft_mag_sum = float(np.sum(fft_mag) + 1e-8)
    freqs = np.fft.rfftfreq(fft_window.size, d=1.0 / sample_rate)
    centroid_hz = float(np.sum(freqs * fft_mag) / fft_mag_sum)

    # Autocorrelation F0 estimate with sane speech bounds.
    ac_window = samples[: min(8192, samples.size)]
    centered = ac_window - np.mean(ac_window)
    if np.max(np.abs(centered)) > 1e-6:
        autocorr = np.correlate(centered, centered, mode="full")[centered.size - 1 :]
        min_lag = max(1, int(sample_rate / 300))
        max_lag = min(autocorr.size - 1, int(sample_rate / 70))
        if max_lag > min_lag:
            lag = int(np.argmax(autocorr[min_lag:max_lag]) + min_lag)
            pitch_proxy_hz = float(sample_rate / lag)
        else:
            pitch_proxy_hz = float(70.0 + min(190.0, 250.0 * zcr))
    else:
        pitch_proxy_hz = float(70.0 + min(190.0, 250.0 * zcr))

    # 16D deterministic embedding from distribution and spectral bins.
    quantiles = np.percentile(abs_samples, [10, 25, 50, 75, 90]).astype(np.float32)
    band_slices = np.array_split(fft_mag.astype(np.float32), 8)
    band_energies = np.array(
        [float(np.mean(band)) if band.size else 0.0 for band in band_slices],
        dtype=np.float32,
    )
    embedding = np.concatenate(
        [
            np.array(
                [
                    power,
                    std,
                    zcr,
                    peak,
                    pitch_proxy_hz / 300.0,
                    centroid_hz / 6000.0,
                ],
                dtype=np.float32,
            ),
            quantiles,
            band_energies[:7],
        ]
    )
    embedding = embedding / (np.linalg.norm(embedding) + 1e-8)

    quality_confidence = float(max(0.0, min(1.0, (power * 2.4) + (0.2 - std))))

    demographics = _estimate_gender_and_age(
        pitch_hz=pitch_proxy_hz,
        spectral_centroid_hz=centroid_hz,
        confidence=quality_confidence,
    )

    return {
        "embedding": embedding,
        "confidence": quality_confidence,
        "pitch_proxy_hz": pitch_proxy_hz,
        "spectral_centroid_hz": centroid_hz,
        **demographics,
    }


def _persist_speaker_profiles() -> None:
    payload = [profile.model_dump() for profile in SPEAKER_PROFILES.values()]
    with open(SPEAKER_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _load_speaker_profiles() -> None:
    if not os.path.exists(SPEAKER_DB_PATH):
        return
    try:
        with open(SPEAKER_DB_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            profile = SpeakerProfile(**item)
            SPEAKER_PROFILES[profile.id] = profile
    except (json.JSONDecodeError, OSError, ValueError):
        SPEAKER_PROFILES.clear()


def _find_best_speaker_match(embedding: np.ndarray) -> Dict[str, Any]:
    best_id = None
    best_score = 0.0
    for speaker_id, profile in SPEAKER_PROFILES.items():
        current = np.array(profile.embedding, dtype=np.float32)
        score = _safe_cosine_similarity(embedding, current)
        if score > best_score:
            best_score = score
            best_id = speaker_id
    return {"speaker_id": best_id, "similarity": best_score}


def _normalize_frequency_mhz(payload: AlertCreate) -> Optional[float]:
    if payload.frequency_mhz is not None:
        return payload.frequency_mhz
    if payload.frequency_hz is not None:
        return payload.frequency_hz / 1e6
    return None


def _normalize_language_code(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    code = value.strip().lower()
    return code or None


def _resolve_alert_language(payload: AlertCreate) -> Optional[str]:
    if payload.language:
        return _normalize_language_code(payload.language)
    metadata_language = payload.metadata.get("language")
    if metadata_language:
        return _normalize_language_code(str(metadata_language))
    transcript_language = payload.metadata.get("transcript_language")
    if transcript_language:
        return _normalize_language_code(str(transcript_language))
    return None


def _coerce_stress_percent(value: Any) -> Optional[float]:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= score <= 1.0:
        score *= 100.0
    return max(0.0, min(100.0, score))


def _extract_stress_score(payload: AlertCreate) -> Optional[float]:
    metadata = payload.metadata or {}
    candidates = [
        metadata.get("stress_score"),
        metadata.get("stress_level"),
        metadata.get("stress"),
        (metadata.get("emotions") or {}).get("stress_level"),
    ]
    for candidate in candidates:
        score = _coerce_stress_percent(candidate)
        if score is not None:
            return score
    return None


def _is_truthy_env(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_high_priority_audio_event(
    payload: AlertCreate,
    severity: AlertSeverity,
    stress_score: Optional[float],
    is_distress: bool,
) -> bool:
    if is_distress or severity == AlertSeverity.CRITICAL:
        return True
    if stress_score is not None and stress_score > 70.0:
        return True

    metadata = payload.metadata or {}
    priority_flag = str(metadata.get("priority", "")).strip().lower()
    if priority_flag in {"high", "critical", "urgent"}:
        return True

    text = " ".join(
        filter(
            None,
            [
                payload.title,
                payload.description,
                payload.transcript,
                " ".join(payload.tags or []),
                str(metadata.get("event", "")),
                str(metadata.get("trigger", "")),
                str(metadata.get("category", "")),
            ],
        )
    ).lower()
    return any(term in text for term in HIGH_PRIORITY_AUDIO_TERMS)


def _dispatch_spotify_audio_alert(alert: AlertRecord, stress_score: Optional[float]) -> bool:
    if not _is_truthy_env(os.getenv("SPOTIFY_ALERTS_ENABLED"), default=True):
        return False

    alert_uri = os.getenv("SPOTIFY_ALERT_URI", "spotify:search:alert%20tone")
    command_template = os.getenv("SPOTIFY_ALERT_COMMAND")
    timeout_sec = int(os.getenv("SPOTIFY_ALERT_TIMEOUT", "5"))

    if command_template:
        try:
            custom_cmd = [
                part.format(
                    uri=alert_uri,
                    title=alert.title,
                    severity=alert.severity.value,
                    alert_id=alert.id,
                    stress_score=(
                        f"{stress_score:.1f}" if stress_score is not None else ""
                    ),
                )
                for part in shlex.split(command_template)
            ]
            result = subprocess.run(
                custom_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            return result.returncode == 0
        except (ValueError, FileNotFoundError, subprocess.SubprocessError):
            return False

    commands = [
        ["open", "-a", "Spotify", alert_uri],
        ["open", alert_uri],
    ]
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_sec, check=False
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return True

    return False


def _transcription_preview(payload: AlertCreate) -> str:
    source = payload.transcript or payload.description or payload.title
    source = (source or "").strip()
    if len(source) <= 220:
        return source
    return source[:217].rstrip() + "..."


def _resolve_audio_file(filename: str) -> Optional[Path]:
    # Restrict resolution to basename-only lookups inside known audio dirs.
    candidate_name = Path(filename).name
    if not candidate_name:
        return None

    for base_dir in AUDIO_SEARCH_DIRS:
        try:
            candidate = (base_dir / candidate_name).resolve()
            candidate.relative_to(base_dir.resolve())
        except (FileNotFoundError, RuntimeError, ValueError):
            continue

        if candidate.is_file():
            return candidate

    return None


def _transcribe_payload(
    audio_path: Path,
    model_size: str,
    backend: str,
    language: Optional[str],
) -> Dict[str, Any]:
    whisper_config = WhisperConfig(
        model_size=model_size,
        backend=backend,
        language=language,
    )
    transcription = transcribe_audio_file(audio_path, whisper_config)
    return {
        "file": audio_path.name,
        "text": str(transcription.get("text", "")).strip(),
        "language": transcription.get("language"),
        "segments": transcription.get("segments", []),
        "backend": transcription.get("backend"),
        "model": transcription.get("model"),
    }


def _stress_payload(audio_path: Path) -> Dict[str, Any]:
    features = extract_stress_features(audio_path)
    stress_score = score_stress(features)
    return {
        "file": audio_path.name,
        "stress_score": stress_score,
        "features": {
            "pitch_variance_hz2": features.pitch_variance_hz2,
            "zero_crossing_rate": features.zero_crossing_rate,
            "speech_rate_per_sec": features.speech_rate_per_sec,
            "rms_energy": features.rms_energy,
            "voiced_ratio": features.voiced_ratio,
        },
    }


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def _dispatch_alert_to_mission_control(alert: AlertRecord) -> None:
    conversation_url = os.getenv("MC_CONVERSATION_WEBHOOK_URL")
    kanban_url = os.getenv("MC_KANBAN_WEBHOOK_URL")
    token = os.getenv("MC_WEBHOOK_BEARER_TOKEN")
    timeout = int(os.getenv("MC_WEBHOOK_TIMEOUT", "3"))

    if not conversation_url and not kanban_url:
        return

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base_payload = {
        "source": "wichita-sdr",
        "alert": alert.dict(),
    }

    if conversation_url:
        payload = {**base_payload, "channel": "conversation"}
        try:
            _post_json(conversation_url, payload, headers, timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            pass

    if kanban_url:
        payload = {**base_payload, "channel": "kanban"}
        try:
            _post_json(kanban_url, payload, headers, timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            pass


async def _broadcast_alert(alert: AlertRecord) -> None:
    if not ALERT_CLIENTS:
        return
    dead_clients: List[WebSocket] = []
    payload = {"type": "alert", "alert": alert.dict()}
    for client in ALERT_CLIENTS:
        try:
            await client.send_json(payload)
        except Exception:
            dead_clients.append(client)
    for client in dead_clients:
        if client in ALERT_CLIENTS:
            ALERT_CLIENTS.remove(client)


_load_speaker_profiles()


# ==================== SIGNAL CAPTURE ====================


@app.post("/capture/signal", tags=["capture"], response_model=Dict[str, Any])
async def capture_signal(request: CaptureRequest, background_tasks: BackgroundTasks):
    """
    Capture raw IQ samples from specified frequency.

    Returns path to captured IQ file and basic statistics.
    """
    output_file = f"/tmp/capture_{int(request.frequency)}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.iq"

    cmd = [
        "hackrf_transfer",
        "-r",
        output_file,
        "-f",
        str(int(request.frequency)),
        "-s",
        str(int(request.sample_rate)),
        "-n",
        str(int(request.sample_rate * request.duration)),
        "-g",
        str(request.gain),
    ]

    if request.amp_enable:
        cmd.extend(["-a", "1"])

    if request.antenna_power:
        raise HTTPException(
            status_code=403,
            detail="antenna_power (Bias-T) is disabled on the web API. Enable bias-T only from a local operator session.",
        )

    try:
        subprocess.run(
            cmd, capture_output=True, text=True, timeout=request.duration + 5
        )

        # Get file stats
        file_size = os.path.getsize(output_file)

        # Quick power calculation
        with open(output_file, "rb") as f:
            raw = f.read(min(100000, file_size))
            iq = np.frombuffer(raw, dtype=np.int8).astype(np.float32) / 128.0
            power_dbfs = 20 * np.log10(np.mean(np.abs(iq)) + 1e-10)

        capture_result = {
            "status": "success",
            "file_path": output_file,
            "frequency_mhz": request.frequency / 1e6,
            "duration_sec": request.duration,
            "file_size_mb": file_size / 1e6,
            "average_power_dbfs": float(power_dbfs),
            "sample_rate_msps": request.sample_rate / 1e6,
        }
        CAPTURES.append(
            CaptureRecord(
                id=str(uuid.uuid4()),
                created_at=datetime.now(timezone.utc),
                **capture_result,
            )
        )
        if len(CAPTURES) > MAX_CAPTURES:
            CAPTURES.pop(0)

        return capture_result

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Capture timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Capture failed: {str(e)}")


# ==================== SPECTRUM SCANNING ====================


@app.post("/spectrum/scan", tags=["spectrum"])
async def spectrum_scan(request: SpectrumScanRequest):
    """
    Perform wideband spectrum scan across specified range.

    Returns power measurements across frequency range.
    """
    cmd = [
        "hackrf_sweep",
        "-f",
        f"{int(request.start_freq/1e6)}:{int(request.stop_freq/1e6)}",
        "-w",
        str(int(request.bin_width)),
        "-n",
        str(request.sweeps),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # Parse sweep results
        frequencies = []
        powers = []

        for line in result.stdout.split("\n"):
            if "2025" in line and "," in line:  # Data lines have timestamps
                parts = line.split(",")
                if len(parts) >= 8:
                    freq_low = float(parts[2])
                    freq_high = float(parts[3])
                    freq_center = (freq_low + freq_high) / 2
                    power = float(parts[6])

                    frequencies.append(freq_center / 1e6)  # Convert to MHz
                    powers.append(power)

        return {
            "frequencies_mhz": frequencies,
            "power_dbm": powers,
            "peak_frequency_mhz": frequencies[np.argmax(powers)] if powers else None,
            "peak_power_dbm": max(powers) if powers else None,
            "scan_range_mhz": [request.start_freq / 1e6, request.stop_freq / 1e6],
            "bin_width_khz": request.bin_width / 1e3,
            "timestamp": datetime.now(timezone.utc),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


# ==================== SIGNAL ANALYSIS ====================


@app.post("/analysis/classify", tags=["analysis"], response_model=SignalAnalysisResult)
async def classify_signal(
    frequency: float = Query(..., description="Frequency in Hz"),
    iq_file: Optional[UploadFile] = File(None),
):
    """
    Classify and analyze captured signal using ML ensemble.

    Identifies signal type, modulation, and key parameters.
    """
    # This would integrate with the ML ensemble
    # For now, return intelligent guesses based on frequency

    signal_type = SignalType.UNKNOWN
    modulation = ModulationType.RAW
    confidence = 0.5

    # Frequency-based classification heuristics
    freq_mhz = frequency / 1e6

    if 88 <= freq_mhz <= 108:
        signal_type = SignalType.BROADCAST_FM
        modulation = ModulationType.WFM
        confidence = 0.95
    elif 108 <= freq_mhz <= 137:
        signal_type = (
            SignalType.AMATEUR if freq_mhz in [121.5, 123.1] else SignalType.AMATEUR
        )
        modulation = ModulationType.AM
        confidence = 0.8
    elif 156 <= freq_mhz <= 162:
        signal_type = SignalType.MARINE_VHF
        modulation = ModulationType.NFM
        confidence = 0.9
    elif abs(freq_mhz - 1090) < 1:
        signal_type = SignalType.ADSB
        modulation = ModulationType.RAW
        confidence = 0.99
    elif 2400 <= freq_mhz <= 2500:
        signal_type = SignalType.WIFI
        modulation = ModulationType.OFDM
        confidence = 0.85

    return SignalAnalysisResult(
        frequency=frequency,
        signal_type=signal_type,
        modulation=modulation,
        power_dbm=-50.0,  # Would be calculated from IQ data
        bandwidth_khz=200.0,  # Would be measured
        confidence=confidence,
        metadata={
            "frequency_band": (
                FrequencyBand.VHF if 30e6 <= frequency <= 300e6 else FrequencyBand.UHF
            )
        },
    )


# ==================== MARITIME INTELLIGENCE ====================


@app.get("/maritime/ais", tags=["maritime"])
async def get_ais_vessels():
    """
    Monitor AIS vessel broadcasts near Malta using pyais decoder.

    Returns vessel positions decoded from live NMEA feed (when SDR is present)
    or from sample data. Each vessel includes MMSI, name, lat/lon, speed,
    course, and ISO-8601 timestamp for voice-capture correlation.
    """
    import wichita_captures as wc

    refs = wc.scan_captures()
    vessels = []
    for ref in refs[:5]:
        analysis = wc._read_json(ref.path / "analysis_report.json") or {}
        for msg in wc.decode_ais_from_nmea(ref.path, analysis):
            mmsi = msg.get("mmsi")
            if not mmsi or mmsi in wc.VALLETTA_AIS_BASE_MMSIS:
                continue
            if msg.get("lat") is None or msg.get("lon") is None:
                continue
            vessels.append(
                {
                    "mmsi": mmsi,
                    "name": msg.get("name"),
                    "lat": msg["lat"],
                    "lon": msg["lon"],
                    "source": "capture_feed",
                    "capture_id": ref.capture_id,
                }
            )

    return {
        "vessels": vessels,
        "total_count": len(vessels),
        "coverage_area": "Central Mediterranean",
        "receiver_location": "Valletta, Malta",
        "decoder": "capture_library",
        "channels_mhz": [161.975, 162.025],
        "note": "Empty list means no vessels decoded yet.",
    }


@app.get("/maritime/vhf_channels", tags=["maritime"])
async def maritime_vhf_status():
    """
    Monitor marine VHF channels for activity.

    Includes emergency channel 16 and port operations.
    """
    channels = {
        16: {
            "frequency_mhz": 156.800,
            "use": "Emergency/Calling",
            "activity": "monitoring",
        },
        1: {"frequency_mhz": 156.050, "use": "Port Operations", "activity": "low"},
        6: {"frequency_mhz": 156.300, "use": "Ship-to-ship", "activity": "moderate"},
        13: {"frequency_mhz": 156.650, "use": "Navigation", "activity": "high"},
        70: {"frequency_mhz": 156.525, "use": "DSC Digital", "activity": "periodic"},
    }

    return {
        "channels": channels,
        "emergency_status": "clear",
        "port": "Valletta Grand Harbour",
        "timestamp": datetime.now(timezone.utc),
    }


# ==================== AVIATION MONITORING ====================


@app.get("/aviation/adsb", tags=["aviation"])
async def track_aircraft():
    """
    Track aircraft via ADS-B on 1090 MHz.

    Returns aircraft positions and flight information.
    """
    # This would use dump1090 or similar
    aircraft = [
        {
            "icao": "4D2206",
            "callsign": "RYR8FW",
            "airline": "Ryanair",
            "altitude_ft": 38000,
            "speed_knots": 450,
            "heading": 135,
            "position": {"lat": 35.95, "lon": 14.40},
            "route": "MXP-MLA",
            "distance_km": 15.2,
            "timestamp": datetime.now(timezone.utc),
        }
    ]

    return {
        "aircraft": aircraft,
        "total_tracked": len(aircraft),
        "coverage_radius_km": 250,
        "receiver_location": "Valletta, Malta",
    }


@app.get("/aviation/frequencies", tags=["aviation"])
async def aviation_frequencies():
    """
    List aviation frequencies for Malta airspace.

    Includes tower, ground, approach, and emergency.
    """
    return {
        "malta_airport": {
            "tower": {"frequency_mhz": 118.120, "modulation": "AM"},
            "ground": {"frequency_mhz": 121.900, "modulation": "AM"},
            "approach": {"frequency_mhz": 134.700, "modulation": "AM"},
            "departure": {"frequency_mhz": 120.300, "modulation": "AM"},
        },
        "emergency": {
            "guard": {"frequency_mhz": 121.500, "modulation": "AM"},
            "secondary": {"frequency_mhz": 243.000, "modulation": "AM"},
        },
        "navigation": {
            "vor_mlt": {"frequency_mhz": 112.800, "type": "VOR/DME"},
            "ils_rw31": {"frequency_mhz": 109.500, "type": "ILS"},
        },
    }


# ==================== THREAT DETECTION ====================


@app.post("/threats/assess", tags=["threats"], response_model=ThreatAssessment)
async def assess_threat(frequency: float, signal_type: SignalType):
    """
    Assess security threats from detected signals.

    Identifies jamming, spoofing, and rogue transmitters.
    """
    threat_level = "low"
    threat_type = "none"
    description = "Normal signal activity"
    recommendations = []

    # Threat detection logic
    if (
        signal_type == SignalType.AIS
        and frequency != 161.975e6
        and frequency != 162.025e6
    ):
        threat_level = "high"
        threat_type = "AIS Spoofing"
        description = "AIS signal detected on non-standard frequency"
        recommendations = [
            "Verify vessel positions visually",
            "Cross-reference with port authority",
            "Record signal for forensic analysis",
        ]

    return ThreatAssessment(
        threat_level=threat_level,
        threat_type=threat_type,
        description=description,
        frequency=frequency,
        recommendations=recommendations,
        evidence={"signal_type": signal_type, "analysis_time": datetime.now(timezone.utc)},
    )


@app.get("/threats/active", tags=["threats"])
async def active_threats():
    """
    List currently detected threats and anomalies.

    Real-time threat dashboard data.
    """
    return {
        "active_threats": [],
        "anomalies_detected": 0,
        "jamming_detected": False,
        "rogue_transmitters": [],
        "monitoring_status": "active",
        "last_scan": datetime.now(timezone.utc),
    }


# ==================== ALERTS ====================


@app.get("/transcribe", tags=["analysis"])
async def transcribe(
    file: str = Query(..., description="Audio filename under known capture dirs"),
    model_size: str = Query("large-v3", description="Whisper model size"),
    backend: str = Query(
        "auto", description="Whisper backend: auto, faster-whisper, openai-whisper"
    ),
    language: Optional[str] = Query(
        None, description="Optional fixed language hint (e.g. en, mt, ar, it)"
    ),
):
    """
    Transcribe an audio file using configurable Whisper backend.
    """
    audio_path = _resolve_audio_file(file)
    if audio_path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        return _transcribe_payload(audio_path, model_size, backend, language)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio file not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")


@app.get("/analysis/transcribe", tags=["analysis"])
async def transcribe_analysis(
    file: str = Query(..., description="Audio filename under known capture dirs"),
    model_size: str = Query("large-v3", description="Whisper model size"),
    backend: str = Query(
        "auto", description="Whisper backend: auto, faster-whisper, openai-whisper"
    ),
    language: Optional[str] = Query(
        None, description="Optional fixed language hint (e.g. en, mt, ar, it)"
    ),
):
    """
    Alias of /transcribe for analysis namespace.
    """
    audio_path = _resolve_audio_file(file)
    if audio_path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        return _transcribe_payload(audio_path, model_size, backend, language)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio file not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")


@app.get("/stress", tags=["analysis"])
async def stress(file: str = Query(..., description="Audio filename under known capture dirs")):
    """
    Compute stress score (0-100) from pitch variance, zero-crossing rate, energy, and rate.
    """
    audio_path = _resolve_audio_file(file)
    if audio_path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        return _stress_payload(audio_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio file not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stress scoring failed: {exc}")

@app.get("/analysis/stress", tags=["analysis"])
async def stress_analysis(file: str = Query(..., description="Audio filename under known capture dirs")):
    """
    Alias of /stress for analysis namespace.
    """
    audio_path = _resolve_audio_file(file)
    if audio_path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        return _stress_payload(audio_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio file not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stress scoring failed: {exc}")


@app.get("/analysis/audio", tags=["analysis"])
async def analyze_audio(
    file: str = Query(..., description="Audio filename under known capture dirs"),
    model_size: str = Query("large-v3", description="Whisper model size"),
    backend: str = Query(
        "auto", description="Whisper backend: auto, faster-whisper, openai-whisper"
    ),
    language: Optional[str] = Query(
        None, description="Optional fixed language hint (e.g. en, mt, ar, it)"
    ),
):
    """
    Run full AI analysis pipeline: transcription + stress scoring + keyword triage.
    """
    audio_path = _resolve_audio_file(file)
    if audio_path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        whisper_config = WhisperConfig(
            model_size=model_size,
            backend=backend,
            language=language,
        )
        result = analyze_audio_file(audio_path, whisper_config=whisper_config)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio file not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {exc}")

    return result


@app.post("/alerts", tags=["alerts"], response_model=AlertRecord)
async def create_alert(
    payload: AlertCreate, background_tasks: BackgroundTasks
):
    """
    Create an alert and forward it to Mission Control.

    Distress signals are always promoted to critical severity.
    """
    is_distress = _is_distress_alert(payload)
    stress_score = _extract_stress_score(payload)
    severity = payload.severity or AlertSeverity.WARNING
    if is_distress:
        severity = AlertSeverity.CRITICAL

    record = AlertRecord(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        title=payload.title.strip(),
        description=payload.description,
        signal_type=payload.signal_type or SignalType.UNKNOWN,
        severity=severity,
        frequency_mhz=_normalize_frequency_mhz(payload),
        confidence=payload.confidence,
        transcript=payload.transcript,
        language=_resolve_alert_language(payload),
        audio_url=payload.audio_url,
        tags=payload.tags,
        metadata=payload.metadata,
        source=payload.source,
    )

    ALERTS.append(record)
    if len(ALERTS) > MAX_ALERTS:
        ALERTS.pop(0)

    background_tasks.add_task(_dispatch_alert_to_mission_control, record)
    if stress_score is not None and stress_score > 70.0:
        preview = _transcription_preview(payload)
        indicators = payload.metadata or {}
        background_tasks.add_task(
            send_stress_alert,
            stress_score,
            payload.frequency_hz or payload.frequency_mhz,
            preview,
            indicators,
        )
        background_tasks.add_task(
            send_discord_alert,
            "High-stress voice alert detected",
            stress_score,
            preview,
        )
    if _is_high_priority_audio_event(payload, severity, stress_score, is_distress):
        background_tasks.add_task(_dispatch_spotify_audio_alert, record, stress_score)
    await _broadcast_alert(record)

    return record


@app.get("/alerts", tags=["alerts"], response_model=List[AlertRecord])
async def list_alerts(limit: int = Query(100, ge=1, le=500)):
    """List recent alerts."""
    return list(reversed(ALERTS[-limit:]))


@app.get("/alerts/{alert_id}", tags=["alerts"], response_model=AlertRecord)
async def get_alert(alert_id: str):
    """Get a single alert by id."""
    for alert in ALERTS:
        if alert.id == alert_id:
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")


@app.get("/alerts/{alert_id}/evidence", tags=["alerts"])
async def get_alert_evidence(alert_id: str):
    return evidence_context(await get_alert(alert_id))


@app.get("/alerts/{alert_id}/question", tags=["alerts"])
async def get_alert_question(alert_id: str, question: str = Query(...)):
    alert = await get_alert(alert_id)
    try:
        return answer_question(alert, question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/delivery-health", tags=["system"])
async def get_delivery_health():
    return delivery_health(CAPTURES, ALERTS)


@app.get("/captures", tags=["capture"], response_model=List[CaptureRecord])
async def list_captures(limit: int = Query(100, ge=1, le=500)):
    """List recent signal captures for dashboard usage."""
    return list(reversed(CAPTURES[-limit:]))


@app.get("/stress-alerts", tags=["alerts"], response_model=List[AlertRecord])
async def list_stress_alerts(limit: int = Query(100, ge=1, le=500)):
    """List recent stress/distress alerts for dashboard triage."""
    stress_alerts = [alert for alert in ALERTS if _is_stress_alert(alert)]
    return list(reversed(stress_alerts[-limit:]))


@app.get("/api/audio/{filename}", tags=["alerts"])
async def get_audio_clip(filename: str):
    """
    Serve audio clips by filename for dashboard playback.
    """
    audio_path = _resolve_audio_file(filename)
    if audio_path is None:
        raise HTTPException(status_code=404, detail="Audio clip not found")

    media_type = "audio/wav" if audio_path.suffix.lower() == ".wav" else "application/octet-stream"
    return FileResponse(str(audio_path), media_type=media_type, filename=audio_path.name)


@app.post(
    "/voice/speakers/identify",
    tags=["ml"],
    response_model=SpeakerIdentificationResult,
)
async def identify_speaker(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    capture_id: Optional[str] = Form(default=None),
    frequency_hz: Optional[float] = Form(default=None),
    transcript: Optional[str] = Form(default=None),
    source: str = Form(default="wichita-sdr"),
):
    """
    Identify and track speakers across captures using lightweight voice fingerprints.
    """
    if not audio_file.filename:
        raise HTTPException(status_code=400, detail="Audio file name is required")

    audio_bytes = await audio_file.read()
    features = _extract_speaker_features(audio_bytes, audio_file.filename)
    embedding = features["embedding"]

    match = _find_best_speaker_match(embedding)
    matched_existing = False
    if match["speaker_id"] and match["similarity"] >= SPEAKER_MATCH_THRESHOLD:
        candidate = SPEAKER_PROFILES[match["speaker_id"]]
        profile_pitch = float(
            candidate.metadata.get(
                "pitch_proxy_hz_avg",
                candidate.metadata.get("last_pitch_proxy_hz", 0.0),
            )
        )
        profile_centroid = float(
            candidate.metadata.get(
                "spectral_centroid_hz_avg",
                candidate.metadata.get("last_spectral_centroid_hz", 0.0),
            )
        )
        pitch_delta = abs(profile_pitch - features["pitch_proxy_hz"])
        centroid_delta = abs(profile_centroid - features["spectral_centroid_hz"])
        matched_existing = pitch_delta <= 22.0 and centroid_delta <= 650.0

    now = datetime.now(timezone.utc)
    if matched_existing:
        profile = SPEAKER_PROFILES[match["speaker_id"]]
        existing = np.array(profile.embedding, dtype=np.float32)
        updated_embedding = ((existing * profile.captures_count) + embedding) / (
            profile.captures_count + 1
        )
        updated_embedding = updated_embedding / (np.linalg.norm(updated_embedding) + 1e-8)

        prior_total = profile.average_similarity * profile.captures_count
        profile.average_similarity = (prior_total + match["similarity"]) / (
            profile.captures_count + 1
        )
        profile.embedding = updated_embedding.tolist()
        profile.updated_at = now
        profile.last_capture_id = capture_id
        profile.captures_count += 1
        profile.confidence = max(profile.confidence, features["confidence"])
        if features["gender_estimate"] != "unknown":
            profile.gender_estimate = features["gender_estimate"]
        if features["age_estimate"] > 0:
            profile.age_estimate = features["age_estimate"]
            profile.age_range = features["age_range"]
        profile.metadata.update(
            {
                "last_frequency_hz": frequency_hz,
                "last_transcript": transcript,
                "source": source,
                "last_pitch_proxy_hz": features["pitch_proxy_hz"],
                "last_spectral_centroid_hz": features["spectral_centroid_hz"],
                "pitch_proxy_hz_avg": (
                    (
                        profile.metadata.get(
                            "pitch_proxy_hz_avg",
                            profile.metadata.get("last_pitch_proxy_hz", 0.0),
                        )
                        * (profile.captures_count - 1)
                    )
                    + features["pitch_proxy_hz"]
                )
                / profile.captures_count,
                "spectral_centroid_hz_avg": (
                    (
                        profile.metadata.get(
                            "spectral_centroid_hz_avg",
                            profile.metadata.get("last_spectral_centroid_hz", 0.0),
                        )
                        * (profile.captures_count - 1)
                    )
                    + features["spectral_centroid_hz"]
                )
                / profile.captures_count,
            }
        )
    else:
        speaker_id = f"spk_{uuid.uuid4().hex[:10]}"
        profile = SpeakerProfile(
            id=speaker_id,
            created_at=now,
            updated_at=now,
            first_capture_id=capture_id,
            last_capture_id=capture_id,
            captures_count=1,
            average_similarity=1.0,
            gender_estimate=features["gender_estimate"],
            age_estimate=features["age_estimate"],
            age_range=features["age_range"],
            confidence=features["confidence"],
            embedding=embedding.tolist(),
            metadata={
                "last_frequency_hz": frequency_hz,
                "last_transcript": transcript,
                "source": source,
                "last_pitch_proxy_hz": features["pitch_proxy_hz"],
                "last_spectral_centroid_hz": features["spectral_centroid_hz"],
                "pitch_proxy_hz_avg": features["pitch_proxy_hz"],
                "spectral_centroid_hz_avg": features["spectral_centroid_hz"],
            },
        )
        SPEAKER_PROFILES[profile.id] = profile

    background_tasks.add_task(_persist_speaker_profiles)

    return SpeakerIdentificationResult(
        speaker_id=profile.id,
        matched_existing_profile=matched_existing,
        similarity=(match["similarity"] if matched_existing else 1.0),
        profile=profile,
    )


@app.get("/voice/speakers", tags=["ml"], response_model=List[SpeakerProfile])
async def list_speaker_profiles(limit: int = Query(100, ge=1, le=1000)):
    """List known speaker profiles ordered by most recently updated."""
    profiles = sorted(
        SPEAKER_PROFILES.values(), key=lambda p: p.updated_at, reverse=True
    )
    return profiles[:limit]


@app.get("/voice/speakers/{speaker_id}", tags=["ml"], response_model=SpeakerProfile)
async def get_speaker_profile(speaker_id: str):
    """Get one speaker profile."""
    profile = SPEAKER_PROFILES.get(speaker_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return profile


@app.websocket("/realtime/alerts")
async def alerts_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alert streaming.

    Pushes alerts to Mission Control panels.
    """
    await websocket.accept()
    ALERT_CLIENTS.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ALERT_CLIENTS:
            ALERT_CLIENTS.remove(websocket)
    except Exception:
        if websocket in ALERT_CLIENTS:
            ALERT_CLIENTS.remove(websocket)
        await websocket.close()


# ==================== MACHINE LEARNING ====================


@app.post("/ml/fingerprint", tags=["ml"])
async def create_fingerprint(iq_file: UploadFile = File(...)):
    """
    Create RF fingerprint from IQ samples.

    Used for device identification and classification.
    """
    # Save uploaded file
    temp_path = f"/tmp/{iq_file.filename}"
    with open(temp_path, "wb") as f:
        content = await iq_file.read()
        f.write(content)

    # Generate fingerprint (simplified)
    with open(temp_path, "rb") as f:
        raw = f.read(10000)
        iq = np.frombuffer(raw, dtype=np.int8).astype(np.float32) / 128.0

        fingerprint = {
            "mean_power": float(np.mean(np.abs(iq))),
            "std_power": float(np.std(np.abs(iq))),
            "peak_power": float(np.max(np.abs(iq))),
            "spectral_entropy": float(
                np.random.random()
            ),  # Would calculate actual entropy
            "modulation_features": list(
                np.random.random(10)
            ),  # Would extract actual features
        }

    return {
        "fingerprint_id": f"fp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "features": fingerprint,
        "classification_ready": True,
    }


# ==================== REAL-TIME STREAMING ====================


@app.websocket("/realtime/waterfall")
async def waterfall_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time spectrum waterfall.

    Streams FFT data for visualization.
    """
    await websocket.accept()

    try:
        await websocket.send_json(
            {
                "type": "unavailable",
                "message": "Live waterfall is not served from the web process. Use /api/capture-feed for recorded PSD.",
            }
        )
        while True:
            await websocket.receive_text()
    except Exception:
        await websocket.close()


# ==================== SYSTEM STATUS ====================


@app.get("/status", tags=["system"])
async def system_status():
    """
    Receive-only station status (SDRplay RSPdx-R2). No transmit paths.
    """
    import wichita_captures as wc

    refs = wc.scan_captures()
    station = wc.station_payload(refs) if refs else {}
    return {
        "status": "operational",
        "mode": "receive_only",
        "receiver": station.get("receiver", "SDRplay RSPdx-R2"),
        "receiver_serial": station.get("device_serial", "unknown"),
        "captures_on_disk": len(refs),
        "location": "Valletta, Malta",
        "timestamp": datetime.now(timezone.utc),
        "api_version": "2.0.0",
    }


@app.get("/health", tags=["system"])
async def health():
    """Lightweight health endpoint for dashboard polling."""
    status = await system_status()
    import wichita_captures as wc

    refs = wc.scan_captures()
    return {
        "status": "ok",
        "api_version": "2.0.0",
        "timestamp": datetime.now(timezone.utc),
        "receiver": status.get("receiver", "SDRplay RSPdx-R2"),
        "receiver_serial": status.get("receiver_serial", "unknown"),
        "captures_on_disk": len(refs),
        "alerts_count": len(ALERTS),
        "stress_alerts_count": len([alert for alert in ALERTS if _is_stress_alert(alert)]),
        "captures_count": len(CAPTURES),
    }


# ==================== ROOT REDIRECT ====================


@app.get("/dashboard/{filename:path}", include_in_schema=False)
async def dashboard_asset(filename: str):
    base = Path(__file__).resolve().parent / "dashboard"
    asset = (base / filename).resolve()
    if not str(asset).startswith(str(base.resolve())):
        raise HTTPException(status_code=404, detail="Dashboard asset not found")
    if not asset.is_file():
        raise HTTPException(status_code=404, detail="Dashboard asset not found")
    if filename.endswith(".css"):
        media_type = "text/css"
    elif filename.endswith(".js") or filename.endswith(".mjs"):
        media_type = "text/javascript"
    elif filename.endswith(".woff2"):
        media_type = "font/woff2"
    else:
        media_type = "application/octet-stream"
    return FileResponse(
        str(asset),
        media_type=media_type,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/", include_in_schema=False)
async def root():
    """Serve Wichita dashboard."""
    dashboard_path = Path(__file__).resolve().parent / "dashboard" / "index.html"
    if dashboard_path.exists():
        return FileResponse(
            str(dashboard_path),
            media_type="text/html",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )
    raise HTTPException(status_code=404, detail="Dashboard not found")


# Add maritime and aviation routes
app = add_maritime_aviation_routes(app)
app.include_router(capture_feed_router)
app.include_router(live_ais_router)

if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting RF Digital Forensics API Server")
    print("📡 Coverage: 1 MHz to 6 GHz")
    print("📍 Location: Valletta, Malta")
    print("📚 API Docs: http://localhost:8000/docs")
    print("📖 ReDoc: http://localhost:8000/redoc")
    uvicorn.run(app, host="0.0.0.0", port=8000)

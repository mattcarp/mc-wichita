"""ICAO VHF airband channel naming (25 kHz and 8.33 kHz) and LMML published table."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

AIRBAND_MIN_MHZ = 118.0
AIRBAND_MAX_MHZ = 137.0
STEP_25_KHZ = 0.025
STEP_833_KHZ = 25.0 / 3.0 / 1000.0  # 0.008333... MHz
_KHZ_TOL = 0.05

ChannelSpacing = Literal["25k", "8.33k"]


class InvalidAirbandChannel(ValueError):
    pass


@dataclass(frozen=True)
class ParsedChannel:
    name_mhz: float
    name_str: str
    spacing: ChannelSpacing
    tuning_hz: int


_CHANNEL_RE = re.compile(r"^\d{3}\.\d{3}$")


def _mhz_from_name(name: str) -> float:
    raw = (name or "").strip()
    if not _CHANNEL_RE.match(raw):
        raise InvalidAirbandChannel(f"Channel name must look like 118.005, got {name!r}")
    mhz = float(raw)
    if not (AIRBAND_MIN_MHZ <= mhz <= AIRBAND_MAX_MHZ):
        raise InvalidAirbandChannel(f"{mhz} MHz is outside airband {AIRBAND_MIN_MHZ}–{AIRBAND_MAX_MHZ}")
    return mhz


def _on_25k_grid(mhz: float) -> bool:
    khz = mhz * 1000.0
    rem = khz % 25.0
    return rem <= _KHZ_TOL or abs(rem - 25.0) <= _KHZ_TOL


def _on_833_grid(mhz: float) -> bool:
    khz = mhz * 1000.0
    rem = khz % (25.0 / 3.0)
    return rem <= _KHZ_TOL or abs(rem - (25.0 / 3.0)) <= _KHZ_TOL


def classify_spacing(mhz: float) -> ChannelSpacing:
    """25 kHz legacy channels vs 8.33 kHz designators (AIP MHz labels are authoritative)."""
    if _on_25k_grid(mhz):
        return "25k"
    if not _on_833_grid(mhz) and not _CHANNEL_RE.match(f"{mhz:.3f}"):
        raise InvalidAirbandChannel(f"{mhz:.3f} MHz is not on a recognised airband channel grid")
    return "8.33k"


def parse_channel_name(name: str) -> ParsedChannel:
    mhz = _mhz_from_name(name)
    spacing = classify_spacing(mhz)
    return ParsedChannel(
        name_mhz=mhz,
        name_str=f"{mhz:.3f}",
        spacing=spacing,
        tuning_hz=int(round(mhz * 1_000_000)),
    )


def tuning_hz_from_channel_name(name: str) -> int:
    return parse_channel_name(name).tuning_hz


def channel_name_from_hz(hz: int, *, spacing: Optional[ChannelSpacing] = None) -> str:
    try:
        hz_i = int(hz)
    except (TypeError, ValueError) as exc:
        raise InvalidAirbandChannel(f"Invalid tuning Hz: {hz!r}") from exc
    mhz = hz_i / 1_000_000.0
    if not (AIRBAND_MIN_MHZ <= mhz <= AIRBAND_MAX_MHZ):
        raise InvalidAirbandChannel(f"{mhz} MHz is outside airband range")
    kind = spacing or classify_spacing(mhz)
    if kind == "25k" and not _on_25k_grid(mhz):
        raise InvalidAirbandChannel(f"{mhz:.6f} MHz is not on the 25 kHz grid")
    return f"{mhz:.3f}"


def nearest_lmml_channel_mhz(freq_mhz: float, channels: List[Dict[str, Any]], *, tolerance_mhz: float = 0.02) -> Optional[Dict[str, Any]]:
    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for ch in channels:
        try:
            f = float(ch["channel_mhz"])
        except (KeyError, TypeError, ValueError):
            continue
        d = abs(f - freq_mhz)
        if d > tolerance_mhz:
            continue
        if best is None or d < best[0]:
            best = (d, ch)
    return best[1] if best else None


def lmml_table_path() -> Path:
    return Path(__file__).resolve().parent / "config" / "lmml_airband_channels.json"


def load_lmml_channels() -> Dict[str, Any]:
    path = lmml_table_path()
    if not path.is_file():
        raise FileNotFoundError(f"LMML channel table missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def lmml_voice_channels_vhf() -> List[Dict[str, Any]]:
    data = load_lmml_channels()
    out: List[Dict[str, Any]] = []
    for ch in data.get("channels") or []:
        try:
            mhz = float(ch["channel_mhz"])
        except (KeyError, TypeError, ValueError):
            continue
        if mhz < 225.0:  # VHF airband only
            out.append(ch)
    return out


def resolve_channel_label(freq_mhz: Optional[float]) -> Optional[str]:
    if freq_mhz is None:
        return None
    ch = nearest_lmml_channel_mhz(float(freq_mhz), lmml_voice_channels_vhf())
    if ch is None:
        return None
    svc = ch.get("service") or "Airband"
    cs = ch.get("callsign") or ""
    role = ch.get("role") or ""
    base = f"{svc}: {cs}".strip(": ")
    if role and role not in ("primary", "guard"):
        return f"{base} ({role})"
    return base
"""Read-only IQ loaders for offline distress decoding (HackRF cs8, SDRangel .sdriq)."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Tuple, Union

import numpy as np

IqSourceKind = Literal["hackrf_cs8", "sdriq", "sdrplay_cs16"]


@dataclass(frozen=True)
class IqCapture:
    """Complex baseband samples with capture metadata."""

    samples: np.ndarray  # complex64
    sample_rate_hz: float
    center_freq_hz: float | None
    source: IqSourceKind
    path: str


def _complex_from_interleaved(i: np.ndarray, q: np.ndarray) -> np.ndarray:
    return (i.astype(np.float32) + 1j * q.astype(np.float32)).astype(np.complex64)


def read_hackrf_cs8(path: Union[str, Path], sample_rate_hz: float) -> IqCapture:
    """HackRF `hackrf_transfer` raw cs8: unsigned 8-bit I then Q interleaved."""
    raw = Path(path).read_bytes()
    u8 = np.frombuffer(raw, dtype=np.uint8)
    if u8.size % 2:
        raise ValueError(f"cs8 file {path!s} has odd byte length")
    i = (u8[0::2].astype(np.float32) - 127.5) / 127.5
    q = (u8[1::2].astype(np.float32) - 127.5) / 127.5
    return IqCapture(
        samples=_complex_from_interleaved(i, q),
        sample_rate_hz=float(sample_rate_hz),
        center_freq_hz=None,
        source="hackrf_cs8",
        path=str(path),
    )


def read_sdriq(path: Union[str, Path]) -> IqCapture:
    """SDRangel `.sdriq` with 32-byte little-endian header (see SDRangel File Input plugin)."""
    p = Path(path)
    hdr = p.read_bytes()[:32]
    if len(hdr) < 32:
        raise ValueError(f"sdriq header too short: {path!s}")
    sample_rate = struct.unpack_from("<I", hdr, 0)[0]
    center_freq = struct.unpack_from("<Q", hdr, 4)[0]
    sample_bits = struct.unpack_from("<I", hdr, 20)[0]
    crc = struct.unpack_from("<I", hdr, 28)[0]
    if (zlib.crc32(hdr[:28]) & 0xFFFFFFFF) != crc:
        raise ValueError(f"sdriq header CRC mismatch: {path!s}")
    payload = p.read_bytes()[32:]
    if sample_bits == 24:
        usable = (len(payload) // 6) * 6
        if usable < 6:
            raise ValueError(f"sdriq payload too short: {path!s}")
        if usable != len(payload):
            # Some recordings retain a partial tail sample; decode complete symbols only.
            payload = payload[:usable]
        raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 6)
        i = (
            (raw[:, 0].astype(np.int32) << 16)
            | (raw[:, 1].astype(np.int32) << 8)
            | raw[:, 2].astype(np.int32)
        )
        q = (
            (raw[:, 3].astype(np.int32) << 16)
            | (raw[:, 4].astype(np.int32) << 8)
            | raw[:, 5].astype(np.int32)
        )
        if (i & 0x800000).any():
            i = np.where(i & 0x800000, i - 0x1000000, i)
        if (q & 0x800000).any():
            q = np.where(q & 0x800000, q - 0x1000000, q)
        scale = 1.0 / float(1 << 23)
        iq = _complex_from_interleaved(i * scale, q * scale)
    elif sample_bits == 16:
        if len(payload) % 4:
            raise ValueError(f"sdriq 16-bit payload length not multiple of 4: {path!s}")
        raw = np.frombuffer(payload, dtype=np.int16)
        i = raw[0::2].astype(np.float32) / 32768.0
        q = raw[1::2].astype(np.float32) / 32768.0
        iq = _complex_from_interleaved(i, q)
    else:
        raise ValueError(f"unsupported sdriq sample size {sample_bits} in {path!s}")
    return IqCapture(
        samples=iq,
        sample_rate_hz=float(sample_rate),
        center_freq_hz=float(center_freq),
        source="sdriq",
        path=str(path),
    )


def read_sdrplay_cs16(path: Union[str, Path], sample_rate_hz: float) -> IqCapture:
    """Interleaved signed 16-bit I/Q (common SDRplay / rx_sdr capture layout)."""
    raw = Path(path).read_bytes()
    s16 = np.frombuffer(raw, dtype=np.int16)
    if s16.size % 2:
        raise ValueError(f"cs16 file {path!s} has odd sample count")
    i = s16[0::2].astype(np.float32) / 32768.0
    q = s16[1::2].astype(np.float32) / 32768.0
    return IqCapture(
        samples=_complex_from_interleaved(i, q),
        sample_rate_hz=float(sample_rate_hz),
        center_freq_hz=None,
        source="sdrplay_cs16",
        path=str(path),
    )


def sniff_iq_format(path: Union[str, Path]) -> IqSourceKind | None:
    p = Path(path)
    if p.suffix.lower() == ".sdriq":
        return "sdriq"
    if p.suffix.lower() in {".iq", ".raw", ".cs8"}:
        return "hackrf_cs8"
    if p.suffix.lower() in {".cs16", ".s16"}:
        return "sdrplay_cs16"
    return None


def load_iq_file(
    path: Union[str, Path],
    *,
    sample_rate_hz: float | None = None,
    format_hint: IqSourceKind | None = None,
) -> IqCapture:
    """Load IQ from path; `sample_rate_hz` required for raw cs8/cs16 without header."""
    p = Path(path)
    kind = format_hint or sniff_iq_format(p)
    if kind == "sdriq":
        return read_sdriq(p)
    if kind == "hackrf_cs8":
        if sample_rate_hz is None:
            raise ValueError("sample_rate_hz required for hackrf cs8 IQ files")
        return read_hackrf_cs8(p, sample_rate_hz)
    if kind == "sdrplay_cs16":
        if sample_rate_hz is None:
            raise ValueError("sample_rate_hz required for sdrplay cs16 IQ files")
        return read_sdrplay_cs16(p, sample_rate_hz)
    raise ValueError(f"cannot infer IQ format for {p!s}")


def nfm_audio_from_iq(
    cap: IqCapture,
    *,
    audio_rate: int = 48_000,
    deviation_hz: float = 5_000.0,
) -> Tuple[np.ndarray, int]:
    """FM discriminator on complex IQ → real audio at `audio_rate` (receive-only demod)."""
    iq = cap.samples
    if iq.size < 8:
        return np.zeros(0, dtype=np.float32), audio_rate
    phase = np.unwrap(np.angle(iq))
    fm = np.diff(phase).astype(np.float32)
    fm -= np.mean(fm)
    decim = max(1, int(round(cap.sample_rate_hz / audio_rate)))
    if decim > 1:
        fm = fm[::decim]
        out_rate = int(cap.sample_rate_hz / decim)
    else:
        out_rate = int(cap.sample_rate_hz)
    # Scale to roughly unit audio; deviation normalisation is approximate for DSC/EPIRB slicers.
    if deviation_hz > 0 and np.max(np.abs(fm)) > 0:
        fm = fm * (0.8 / np.max(np.abs(fm)))
    return fm.astype(np.float32), out_rate

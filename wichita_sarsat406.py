"""
COSPAS-SARSAT 406 MHz first-generation (FGB) beacon decode — receive-only.

Demodulator FM path ported from HTCommander (Apache-2.0, Ylian Saint-Hilaire 2026),
which traces to dec406 / moricef reference. Frame decoder follows C/S T.001 v1g layout.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

_SYMBOL_RATE = 400
_BIT_SYNC_LEN = 15
_FSYNC_NORMAL = "000101111"
_FSYNC_SELF_TEST = "011010000"

_G1 = [1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
_G2 = [1, 0, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1]


class SarsatProtocol(str, Enum):
    UNKNOWN = "unknown"
    STANDARD_LOCATION = "standard_location"
    NATIONAL_LOCATION = "national_location"
    USER = "user"
    TEST = "test"
    EMERGENCY_ELT = "emergency_elt"
    RLS_LOCATION = "rls_location"
    SHIP_SECURITY = "ship_security"


@dataclass
class Sarsat406Frame:
    length_bits: int
    crc1_ok: bool
    crc2_ok: bool
    country_code: int
    protocol_code: int
    protocol: SarsatProtocol
    hex_id: str
    identification: str
    latitude: Optional[float]
    longitude: Optional[float]
    is_test: bool
    beacon_type: str
    bits: List[int]

    @property
    def valid(self) -> bool:
        return self.crc1_ok and self.crc2_ok

    def to_dict(self) -> Dict[str, Any]:
        return {
            "length_bits": self.length_bits,
            "crc1_ok": self.crc1_ok,
            "crc2_ok": self.crc2_ok,
            "country_code": self.country_code,
            "protocol_code": self.protocol_code,
            "protocol": self.protocol.value,
            "hex_id": self.hex_id,
            "identification": self.identification,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_test": self.is_test,
            "beacon_type": self.beacon_type,
            "valid": self.valid,
        }


def _get_bits(s: List[int], start: int, length: int) -> int:
    v = 0
    for i in range(length):
        v = (v << 1) | (s[start + i] & 1)
    return v


def _crc_remainder(s: List[int], g: List[int], start_bit: int, end_bit: int, glen: int) -> int:
    div = [s[start_bit + j] & 1 for j in range(glen)]
    i = start_bit
    while i < end_bit:
        for j in range(glen):
            div[j] ^= g[j]
        while div[0] == 0 and i < end_bit:
            for j in range(glen - 1):
                div[j] = div[j + 1]
            div[glen - 1] = (s[i + glen] & 1) if i < end_bit - 1 else 0
            i += 1
    return sum(div)


def _crc1(s: List[int]) -> int:
    return _crc_remainder(s, _G1, 24, 85, 22)


def _crc2(s: List[int]) -> int:
    return _crc_remainder(s, _G2, 106, 132, 13)


def _correct(s: List[int], crc_fn, lo: int, hi: int) -> int:
    if crc_fn(s) == 0:
        return 0
    for i in range(lo, hi + 1):
        s[i] ^= 1
        if crc_fn(s) == 0:
            return 1
        s[i] ^= 1
    for i in range(lo, hi + 1):
        s[i] ^= 1
        for j in range(i + 1, hi + 1):
            s[j] ^= 1
            if crc_fn(s) == 0:
                return 2
            s[j] ^= 1
        s[i] ^= 1
    for i in range(lo, hi + 1):
        s[i] ^= 1
        for j in range(i + 1, hi + 1):
            s[j] ^= 1
            for k in range(j + 1, hi + 1):
                s[k] ^= 1
                if crc_fn(s) == 0:
                    return 3
                s[k] ^= 1
            s[j] ^= 1
        s[i] ^= 1
    return -1


def has_sync(bits: List[int]) -> bool:
    if len(bits) < 24:
        return False
    if any(bits[i] != 1 for i in range(15)):
        return False
    fs = "".join(str(b) for b in bits[15:24])
    return fs in (_FSYNC_NORMAL, _FSYNC_SELF_TEST)


def _classify(s: List[int], length: int, code: int) -> SarsatProtocol:
    flag = s[25]
    if length == 112:
        if flag != 1:
            return SarsatProtocol.UNKNOWN
        return SarsatProtocol.TEST if (code & 0x7) == 7 else SarsatProtocol.USER
    if flag == 0:
        mapping = {
            2: SarsatProtocol.STANDARD_LOCATION,
            3: SarsatProtocol.STANDARD_LOCATION,
            4: SarsatProtocol.STANDARD_LOCATION,
            5: SarsatProtocol.STANDARD_LOCATION,
            6: SarsatProtocol.STANDARD_LOCATION,
            7: SarsatProtocol.STANDARD_LOCATION,
            8: SarsatProtocol.NATIONAL_LOCATION,
            9: SarsatProtocol.EMERGENCY_ELT,
            10: SarsatProtocol.NATIONAL_LOCATION,
            11: SarsatProtocol.NATIONAL_LOCATION,
            12: SarsatProtocol.SHIP_SECURITY,
            13: SarsatProtocol.RLS_LOCATION,
            14: SarsatProtocol.TEST,
            15: SarsatProtocol.TEST,
        }
        return mapping.get(code, SarsatProtocol.UNKNOWN)
    return SarsatProtocol.USER


def _identify(s: List[int], proto: SarsatProtocol, code: int) -> str:
    if proto in (SarsatProtocol.STANDARD_LOCATION, SarsatProtocol.SHIP_SECURITY):
        id_data = _get_bits(s, 40, 24)
        if code in (2, 12):
            mmsi = (id_data >> 4) & 0xFFFFF
            return f"MMSI last6: {mmsi}"
        if code == 3:
            return f"Aircraft {id_data & 0xFFFFFF:06X}"
        if code in (4, 6, 7):
            tac = (id_data >> 14) & 0x3FF
            serial = id_data & 0x3FFF
            return f"TAC: {tac}, Serial: {serial}"
        if code == 5:
            op = (id_data >> 9) & 0x7FFF
            serial = id_data & 0x1FF
            return f"Operator: {op:X}, Serial: {serial}"
        return f"ID: {id_data:X}"
    if proto == SarsatProtocol.EMERGENCY_ELT:
        if _get_bits(s, 40, 2) == 0:
            addr = _get_bits(s, 42, 24)
            return f"Aircraft {addr:06X}"
        return "ID not available"
    return ""


def _hex15(s: List[int], proto: SarsatProtocol) -> str:
    id_hi = 0
    id_lo = 0
    for i in range(25, 85):
        bit = s[i] & 1
        id_hi = ((id_hi << 1) | (id_lo >> 31)) & 0xFFFFFFFF
        id_lo = ((id_lo << 1) | bit) & 0xFFFFFFFF
    id_hi &= 0x0FFFFFFF
    if proto in (SarsatProtocol.STANDARD_LOCATION, SarsatProtocol.SHIP_SECURITY):
        id_lo = (id_lo & 0xFFE00000) | 0x000FFBFF
    elif proto == SarsatProtocol.NATIONAL_LOCATION:
        id_lo = (id_lo & 0xF8000000) | 0x03F81FE0
    elif proto in (SarsatProtocol.RLS_LOCATION, SarsatProtocol.EMERGENCY_ELT):
        id_lo = (id_lo & 0xFFF80000) | 0x0003FDFF
    return f"{id_hi:07X}{id_lo:08X}"


def _valid_coord(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _position(s: List[int], length: int, proto: SarsatProtocol) -> Optional[Tuple[float, float]]:
    if proto in (SarsatProtocol.STANDARD_LOCATION, SarsatProtocol.SHIP_SECURITY):
        lat = _get_bits(s, 65, 9) * 0.25
        if s[64] == 1:
            lat = -lat
        lon = _get_bits(s, 75, 10) * 0.25
        if s[74] == 1:
            lon = -lon
        if length == 144 and _get_bits(s, 106, 4) == 0xD:
            lat_sign = 1 if s[112] == 1 else -1
            lat += lat_sign * (_get_bits(s, 113, 5) / 60.0 + (_get_bits(s, 118, 4) * 4) / 3600.0)
            lon_sign = 1 if s[122] == 1 else -1
            lon += lon_sign * (_get_bits(s, 123, 5) / 60.0 + (_get_bits(s, 128, 4) * 4) / 3600.0)
        return (lat, lon) if _valid_coord(lat, lon) else None
    if proto == SarsatProtocol.USER and length == 144:
        if _get_bits(s, 36, 3) == 0:
            return None
        lat_sign = 1 if s[107] == 0 else -1
        lat = lat_sign * (_get_bits(s, 108, 7) + (_get_bits(s, 115, 4) * 4.0) / 60.0)
        lon_sign = 1 if s[119] == 0 else -1
        lon = lon_sign * (_get_bits(s, 120, 8) + (_get_bits(s, 128, 4) * 4.0) / 60.0)
        return (lat, lon) if _valid_coord(lat, lon) else None
    if proto == SarsatProtocol.EMERGENCY_ELT and length == 144:
        lat = _get_bits(s, 67, 8) * 0.5
        if s[66] == 1:
            lat = -lat
        lon = _get_bits(s, 76, 9) * 0.5
        if s[75] == 1:
            lon = -lon
        if _get_bits(s, 112, 2) > 0:
            lat_sign = 1 if s[114] == 1 else -1
            lat += lat_sign * (_get_bits(s, 115, 4) / 60.0 + (_get_bits(s, 119, 4) * 4) / 3600.0)
            lon_sign = 1 if s[123] == 1 else -1
            lon += lon_sign * (_get_bits(s, 124, 4) / 60.0 + (_get_bits(s, 128, 4) * 4) / 3600.0)
        return (lat, lon) if _valid_coord(lat, lon) else None
    return None


def _beacon_type_label(proto: SarsatProtocol, code: int) -> str:
    if proto == SarsatProtocol.EMERGENCY_ELT:
        return "ELT(DT)"
    if proto == SarsatProtocol.SHIP_SECURITY:
        return "SSAS"
    if proto in (SarsatProtocol.STANDARD_LOCATION, SarsatProtocol.NATIONAL_LOCATION):
        if code in (2, 12):
            return "EPIRB (MMSI)"
        return "EPIRB/PLB location"
    if proto == SarsatProtocol.TEST:
        return "self-test"
    if proto == SarsatProtocol.USER:
        return "PLB/user"
    return "406 beacon"


def decode_frame_bits(bits: List[int]) -> Optional[Sarsat406Frame]:
    if len(bits) not in (112, 144):
        return None
    work = list(bits)
    length = len(work)
    padded = work if length == 144 else work + [0] * 32
    c1 = _correct(padded, _crc1, 24, 105)
    crc1_ok = c1 >= 0
    c2 = 0
    crc2_ok = True
    if length == 144:
        user_code = _get_bits(padded, 36, 3)
        is_orbitography = padded[25] == 1 and user_code == 0
        if not is_orbitography:
            c2 = _correct(padded, _crc2, 106, 131)
            crc2_ok = c2 >= 0
    country = _get_bits(padded, 26, 10)
    protocol_code = _get_bits(padded, 36, 4)
    is_test = "".join(str(b) for b in padded[15:24]) == _FSYNC_SELF_TEST
    proto = _classify(padded, length, protocol_code)
    ident = _identify(padded, proto, protocol_code)
    pos = _position(padded, length, proto)
    hex_id = _hex15(padded, proto)
    return Sarsat406Frame(
        length_bits=length,
        crc1_ok=crc1_ok,
        crc2_ok=crc2_ok,
        country_code=country,
        protocol_code=protocol_code,
        protocol=proto,
        hex_id=hex_id,
        identification=ident,
        latitude=pos[0] if pos else None,
        longitude=pos[1] if pos else None,
        is_test=is_test,
        beacon_type=_beacon_type_label(proto, protocol_code),
        bits=work,
    )


def _capture_trame(pcm: np.ndarray, start: int, nb: int) -> Tuple[Optional[str], int]:
    """FM-demod biphase-L slicer (dec406 capture_trame), ported from HTCommander."""
    two_nb = 2 * nb
    n = len(pcm)
    y = np.zeros(two_nb, dtype=np.float64)
    coeff = 100.0
    k = num_bit = synchro = depart = cpte = 0
    longueur = 144
    etat = -1
    s = [-1] * 150
    mx = 1e4
    mn = -1e4
    seuil1 = mx / coeff
    seuil0 = mn / coeff
    i = start
    while num_bit < longueur and i < n:
        ech = float(pcm[i])
        i += 1
        k = (k + 1) % two_nb
        y[k] = ech
        ymoy = float(np.sum(y) / two_nb)
        y1 = 0.0
        for j in range(nb):
            y1 += (y[(k + j) % two_nb] - ymoy) * (y[(k + j + nb) % two_nb] - ymoy)
        if y1 > mx:
            mx = y1
            seuil1 = mx / coeff
        if y1 < mn:
            mn = y1
            seuil0 = mn / coeff
        if synchro == 0:
            if depart == 0:
                if y1 > seuil1:
                    depart = 1
                cpte = 0
            else:
                cpte += 1
                if y1 < seuil0:
                    nb15 = cpte // nb
                    if 12 <= nb15 <= 18:
                        synchro = 1
                        cpte = 0
                        for x in range(15):
                            s[x] = 1
                        num_bit = 15
                        etat = 0
                    else:
                        cpte = depart = synchro = 0
                        etat = -1
                        num_bit = 0
        else:
            cpte += 1
            if s[24] == 0:
                longueur = 112
            if y1 > seuil1:
                if etat == 0:
                    etat = 1
                    cpte -= nb // 2
                    while cpte > 0 and num_bit < longueur:
                        s[num_bit] = 0 if s[num_bit - 1] == 1 else 1
                        num_bit += 1
                        cpte -= nb
                    cpte = 0
            elif y1 < seuil0:
                if etat == 1:
                    etat = 0
                    cpte -= nb // 2
                    while cpte > 0 and num_bit < 149:
                        s[num_bit] = s[num_bit - 1]
                        num_bit += 1
                        cpte -= nb
                    cpte = 0
    if num_bit >= longueur:
        bits = "".join("1" if s[j] == 1 else "0" for j in range(longueur))
        return bits, i
    return None, i


def demod_pcm_int16(pcm: np.ndarray, sample_rate: int) -> List[Sarsat406Frame]:
    nb = int(round(sample_rate / _SYMBOL_RATE))
    if nb < 4 or len(pcm) < nb * 40:
        return []
    seen: Dict[str, Sarsat406Frame] = {}
    pos = 0
    guard = 0
    while pos < len(pcm) - nb * 40 and guard < 64:
        guard += 1
        bitstr, pos = _capture_trame(pcm, pos, nb)
        if bitstr is None:
            break
        bits = [1 if c == "1" else 0 for c in bitstr]
        frame = decode_frame_bits(bits)
        if frame and frame.crc1_ok and (frame.length_bits == 112 or frame.crc2_ok):
            seen["".join(str(b) for b in frame.bits)] = frame
    return list(seen.values())


def load_wav_pcm(path: Path) -> Tuple[np.ndarray, int]:
    rate, data = wavfile.read(str(path))
    if data.dtype == np.int16:
        pcm = data.astype(np.int32)
    elif data.dtype == np.int32:
        pcm = data
    elif data.dtype == np.uint8:
        pcm = (data.astype(np.int32) - 128) * 256
    else:
        pcm = (data.astype(np.float32) * 32767.0).astype(np.int32)
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1).astype(np.int32)
    return pcm, int(rate)


def decode_from_audio_wav(path: Path, target_rate: int = 32_000) -> List[Sarsat406Frame]:
    pcm, rate = load_wav_pcm(path)
    if rate != target_rate:
        pcm = resample_poly(pcm, target_rate, rate).astype(np.int32)
        rate = target_rate
    return demod_pcm_int16(pcm, rate)


def decode_from_fm_audio(audio: np.ndarray, sample_rate: int) -> List[Sarsat406Frame]:
    """Decode from float FM-demod audio (e.g. after `nfm_audio_from_iq`)."""
    if audio.size == 0:
        return []
    target = 32_000
    if sample_rate != target:
        audio = resample_poly(audio, target, sample_rate).astype(np.float32)
        sample_rate = target
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int32)
    return demod_pcm_int16(pcm, sample_rate)

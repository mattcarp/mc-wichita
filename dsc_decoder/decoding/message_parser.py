"""
DSC message parser using ITU-R M.493 structure.

DSC message layout after dot pattern:
    Phasing block (16 symbols on-air):
        DX: 125 125 125 125 125 125 [fmt] [fmt]
        RX: 111 110 109 108 107 106 105  104
    Message body (DX info stream extracted from every-other on-air symbol):
        info[0..4]   Address MMSI (10 digits, last is filler -> 9-digit MMSI)
        info[5]      Category (100=Routine, 108=Safety, 110=Urgency, 112=Distress)
        info[6..10]  Self-ID MMSI
        info[11]     Telecommand 1
        info[12+]    Format-specific fields (distress data, frequency, ...)
        ...
        info[N-1]    ECC (XOR check character)
        info[N]      EOS marker (117 RQ / 122 BQ / 127 EOS)
"""

from typing import List, Tuple, Optional, Dict, Any
from ..protocol.constants import (
    SYMBOL_EOS, SYMBOL_RQ, SYMBOL_BQ, SYMBOL_PREAMBLE, FORMAT_CODES,
    CATEGORY_CODES, TELECOMMAND_1_CODES, TELECOMMAND_2_CODES,
    DISTRESS_NATURE, POSITION_QUADRANT,
)


PHASING_LEN = 16
PHASING_FMT_DX_OFFSET = 12

# A symbol value in [0..99] encodes 2 decimal digits; values >=100 are special
# (TC codes, EOS markers, "no info" filler 126, etc.)
NO_INFO = 126


def _two_digits(symbol: int) -> Optional[str]:
    """Return 2-digit string for a symbol in 0..99 (else None)."""
    if 0 <= symbol <= 99:
        return f"{symbol:02d}"
    return None


def _digits(symbols: List[int]) -> Optional[str]:
    """Concatenate 2-digit strings; None if any symbol is non-digit (>99)."""
    parts = [_two_digits(s) for s in symbols]
    if any(p is None for p in parts):
        return None
    return ''.join(parts)


def _decode_mmsi(symbols: List[int]) -> Optional[str]:
    """5 symbols -> 9-digit MMSI string (10 digits on-wire, last is filler)."""
    d = _digits(symbols)
    return d[:9] if d else None


def _decode_position(symbols: List[int]) -> Optional[Dict[str, Any]]:
    """5 symbols -> position dict (Q DD MM DDD MM => lat/lon).

    Quadrant: 0=NE 1=NW 2=SE 3=SW. Returns None if any field is invalid or
    encoded as 'no position' (all-9s)."""
    if len(symbols) < 5:
        return None
    d = _digits(symbols)
    if d is None or len(d) < 10:
        return None
    if d == '9' * 10:
        return None  # explicit "no position"

    try:
        q = int(d[0])
        lat_deg = int(d[1:3])
        lat_min = int(d[3:5])
        lon_deg = int(d[5:8])
        lon_min = int(d[8:10])
    except ValueError:
        return None

    if q > 3 or lat_deg > 90 or lat_min > 59 or lon_deg > 180 or lon_min > 59:
        return None

    lat_dir, lon_dir = POSITION_QUADRANT[q]
    lat = lat_deg + lat_min / 60.0
    lon = lon_deg + lon_min / 60.0
    if lat_dir == 'S':
        lat = -lat
    if lon_dir == 'W':
        lon = -lon

    return {
        'lat': lat,
        'lon': lon,
        'lat_str': f"{lat_deg}°{lat_min:02d}′{lat_dir}",
        'lon_str': f"{lon_deg}°{lon_min:02d}′{lon_dir}",
        'quadrant': q,
    }


def _decode_time(symbols: List[int]) -> Optional[str]:
    """2 symbols -> 'HH:MM UTC' string. 8888 = 'no time'."""
    if len(symbols) < 2:
        return None
    d = _digits(symbols)
    if d is None or len(d) < 4:
        return None
    if d == '8888':
        return None
    try:
        hh = int(d[0:2])
        mm = int(d[2:4])
    except ValueError:
        return None
    if hh > 23 or mm > 59:
        return None
    return f"{hh:02d}:{mm:02d} UTC"


def _decode_frequency(symbols: List[int]) -> Optional[Dict[str, Any]]:
    """3 symbols (6 digits) -> frequency/channel info per M.493 Annex 3.

    Observed formats from captured coast-station broadcasts:
      9000XX -> VHF simplex channel XX (e.g. 900066 = Ch 66, 900016 = Ch 16)
      9100XX -> VHF duplex channel XX
      All-9s -> no information
    HF frequencies are encoded as 100 Hz units (not currently decoded)."""
    if len(symbols) < 3:
        return None
    d = _digits(symbols)
    if d is None or len(d) < 6:
        return None

    if d == '9' * 6:
        return None

    if d.startswith('9000') and d[4:6].isdigit():
        ch = int(d[4:6])
        return {'type': 'vhf_channel', 'channel': ch,
                'description': f"VHF Channel {ch} (simplex)", 'raw': d}
    if d.startswith('9100') and d[4:6].isdigit():
        ch = int(d[4:6])
        return {'type': 'vhf_channel', 'channel': ch,
                'description': f"VHF Channel {ch} (duplex)", 'raw': d}

    return {'type': 'raw', 'description': f"Freq code {d}", 'raw': d}


def find_phasing(symbols: List[int]) -> Optional[int]:
    """Locate first ITU-R M.493 phasing block."""
    for i in find_all_phasings(symbols):
        return i
    return None


def find_all_phasings(symbols: List[int]):
    """Yield indices of every distinct phasing block in the stream."""
    last = -100
    for i in range(len(symbols) - 6):
        if symbols[i] == SYMBOL_PREAMBLE and symbols[i + 2] == SYMBOL_PREAMBLE:
            r = symbols[i + 1]
            if r in (109, 110, 111) and symbols[i + 3] == r - 1:
                if i + 5 < len(symbols) and symbols[i + 4] == SYMBOL_PREAMBLE \
                        and symbols[i + 5] == r - 2:
                    if i - last > 30:
                        yield i
                        last = i


def _find_eos(info: List[int], start: int = 12) -> Optional[Tuple[int, str]]:
    """Find the FIRST EOS marker in info[start:].

    Returns (position, marker_name) or None."""
    for i in range(start, len(info)):
        if info[i] == SYMBOL_RQ:
            return i, "RQ"
        if info[i] == SYMBOL_BQ:
            return i, "BQ"
        if info[i] == SYMBOL_EOS:
            return i, "EOS"
    return None


def _compute_ecc(symbols: List[int]) -> int:
    """XOR of all symbols modulo 128 (7-bit ECC)."""
    out = 0
    for s in symbols:
        out ^= s & 0x7F
    return out


class DSCMessage:
    """Decoded DSC message with all M.493 fields."""

    def __init__(self):
        self.format_specifier: Optional[str] = None
        self.format_code: Optional[int] = None

        # Common header
        self.address: Optional[str] = None
        self.category: Optional[str] = None
        self.category_code: Optional[int] = None
        self.self_id: Optional[str] = None

        # Telecommands
        self.tc1: Optional[str] = None
        self.tc1_code: Optional[int] = None
        self.tc2: Optional[str] = None
        self.tc2_code: Optional[int] = None

        # Distress-relay specific
        self.distress_mmsi: Optional[str] = None
        self.distress_nature: Optional[str] = None
        self.distress_nature_code: Optional[int] = None

        # Position/time
        self.position: Optional[Dict[str, Any]] = None
        self.time_utc: Optional[str] = None

        # Frequency / subsequent communication
        self.frequency: Optional[Dict[str, Any]] = None

        # End-of-sequence and integrity
        self.eos_marker: Optional[str] = None
        self.ecc_received: Optional[int] = None
        self.ecc_computed: Optional[int] = None
        self.ecc_valid: Optional[bool] = None

        # Raw / debug data
        self.info_symbols: List[int] = []
        self.raw_symbols: List[int] = []
        self.phasing_idx: Optional[int] = None
        self.is_valid: bool = False
        self.confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'format': self.format_specifier,
            'format_code': self.format_code,
            'address_mmsi': self.address,
            'category': self.category,
            'self_id_mmsi': self.self_id,
            'tc1': self.tc1,
            'tc2': self.tc2,
            'distress_mmsi': self.distress_mmsi,
            'distress_nature': self.distress_nature,
            'position': self.position,
            'time_utc': self.time_utc,
            'frequency': self.frequency,
            'eos_marker': self.eos_marker,
            'ecc_valid': self.ecc_valid,
            'is_valid': self.is_valid,
            'confidence': self.confidence,
        }


class MessageParser:
    """Parses DSC symbol streams into DSCMessage instances."""

    def parse(self, symbols_with_validity: List[Tuple[int, bool]]) -> DSCMessage:
        msg = DSCMessage()
        if not symbols_with_validity:
            return msg

        symbols = [s for s, _ in symbols_with_validity]
        validity = [v for _, v in symbols_with_validity]
        msg.raw_symbols = symbols
        msg.confidence = sum(validity) / len(validity) if validity else 0.0

        ph = find_phasing(symbols)
        if ph is None:
            return msg
        msg.phasing_idx = ph

        # Format spec at DX position 12 (and 14, redundant copy)
        fmt_idx = ph + PHASING_FMT_DX_OFFSET
        if fmt_idx >= len(symbols):
            return msg
        msg.format_code = symbols[fmt_idx]
        msg.format_specifier = FORMAT_CODES.get(msg.format_code,
                                                f"Unknown ({msg.format_code})")

        # DX info stream after phasing block
        msg_start = ph + PHASING_LEN
        info: List[int] = []
        k = 0
        while msg_start + 2 * k < len(symbols):
            info.append(symbols[msg_start + 2 * k])
            k += 1
        msg.info_symbols = info

        # --- Common header (all formats with addressed call) ---
        if len(info) < 11:
            return msg

        msg.address = _decode_mmsi(info[0:5])
        msg.category_code = info[5]
        msg.category = CATEGORY_CODES.get(info[5])
        msg.self_id = _decode_mmsi(info[6:11])

        # --- Telecommand 1 ---
        if len(info) > 11:
            msg.tc1_code = info[11]
            msg.tc1 = TELECOMMAND_1_CODES.get(info[11])

        # --- Find EOS marker (defines end of message) ---
        eos = _find_eos(info, start=12)
        if eos:
            eos_idx, eos_name = eos
            msg.eos_marker = eos_name

            # ECC sits immediately before EOS marker
            if eos_idx >= 1:
                msg.ecc_received = info[eos_idx - 1]
                # ECC is XOR over format spec + info[0..ecc_pos-1]
                ecc_input = [msg.format_code] + info[:eos_idx - 1]
                msg.ecc_computed = _compute_ecc(ecc_input)
                msg.ecc_valid = (msg.ecc_received == msg.ecc_computed)

        # --- Format-specific fields ---
        # Individual (120): TC1 + [distress-relay payload | TC2 + freq]
        # Area/Group/Individual-auto (102, 114, 123): TC1 + TC2 + freq
        # All ships (116) and Distress (112) have no address field and
        # re-interpret the header in their own parsers below.
        body_end = (eos[0] - 1) if eos else len(info)  # everything before ECC

        if msg.format_code == 120:
            self._parse_distress_relay(msg, info, body_end)
        elif msg.format_code in (102, 114, 123):
            self._parse_call_with_freq(msg, info, body_end)
        elif msg.format_code == 116:
            self._parse_all_ships(msg, info, body_end)
        elif msg.format_code == 112:
            self._parse_distress(msg, info, body_end)

        msg.is_valid = (msg.format_code in FORMAT_CODES
                        and msg.address is not None
                        and msg.self_id is not None
                        and msg.confidence > 0.7)
        return msg

    def _parse_distress_relay(self, msg: DSCMessage, info: List[int], body_end: int):
        """Individual call (120) has two observed sub-layouts:

        Standard M.493 (full distress data):
            info[11]    TC1 = 112 "Distress relay"
            info[12..16] distress vessel MMSI
            info[17]    nature of distress
            info[18..22] position
            info[23..24] time
            info[25..27] subsequent comm freq

        Short test/broadcast variant (routine coast-station sends):
            info[11]    TC1 = 100/118 (test/voice mode)
            info[12]    TC2 = 126 "no info"
            info[13..15] subsequent comm freq
            info[16..18] freq repeated for redundancy
        """
        # Try standard distress-relay layout first
        if body_end >= 17 and msg.tc1_code == 112:
            mmsi = _decode_mmsi(info[12:17])
            if mmsi and mmsi != "999999999":
                msg.distress_mmsi = mmsi
            if body_end >= 18:
                nature_code = info[17]
                if nature_code in DISTRESS_NATURE:
                    msg.distress_nature_code = nature_code
                    msg.distress_nature = DISTRESS_NATURE[nature_code]
            if body_end >= 23:
                pos = _decode_position(info[18:23])
                if pos:
                    msg.position = pos
            if body_end >= 25:
                t = _decode_time(info[23:25])
                if t:
                    msg.time_utc = t
            if body_end >= 28:
                f = _decode_frequency(info[25:28])
                if f:
                    msg.frequency = f
            return

        # Fallback: short broadcast/test variant. Only attempt TC2/freq if
        # info[12] looks like a real telecommand-2 (>=100) rather than a
        # digit pair (which would indicate the next repetition is overlapping
        # the parse window — common in 5x-redundant DSC transmissions).
        if body_end >= 13 and info[12] >= 100:
            msg.tc2_code = info[12]
            msg.tc2 = TELECOMMAND_2_CODES.get(info[12])
            if body_end >= 16:
                f = _decode_frequency(info[13:16])
                # Only accept VHF channels — raw freq codes are usually
                # MMSI digits from message repetition, not real frequencies
                if f and f.get('type') == 'vhf_channel':
                    msg.frequency = f

    def _parse_all_ships(self, msg: DSCMessage, info: List[int], body_end: int):
        """All ships call (116) has no address field — the info stream
        starts directly with the category:

            info[0]      category
            info[1..5]   self-ID
            info[6]      TC1

        Distress ack/relay (TC1 110/112) then carries the distress payload
        (same content as the original distress alert):
            info[7..11]  distress vessel MMSI
            info[12]     nature of distress
            info[13..17] position
            info[18..19] time

        Other all-ships calls: TC2 at info[7], frequency at info[8..10]."""
        msg.address = "ALL SHIPS"
        msg.category_code = info[0]
        msg.category = CATEGORY_CODES.get(info[0])
        if body_end >= 6:
            msg.self_id = _decode_mmsi(info[1:6])
        if body_end < 7:
            return
        msg.tc1_code = info[6]
        msg.tc1 = TELECOMMAND_1_CODES.get(info[6])

        if msg.tc1_code in (110, 112):
            if body_end >= 12:
                mmsi = _decode_mmsi(info[7:12])
                if mmsi:
                    msg.distress_mmsi = mmsi
            if body_end >= 13 and info[12] in DISTRESS_NATURE:
                msg.distress_nature_code = info[12]
                msg.distress_nature = DISTRESS_NATURE[info[12]]
            if body_end >= 18:
                pos = _decode_position(info[13:18])
                if pos:
                    msg.position = pos
            if body_end >= 20:
                t = _decode_time(info[18:20])
                if t:
                    msg.time_utc = t
        else:
            if body_end >= 8:
                msg.tc2_code = info[7]
                msg.tc2 = TELECOMMAND_2_CODES.get(info[7])
            if body_end >= 11:
                f = _decode_frequency(info[8:11])
                if f:
                    msg.frequency = f

    def _parse_call_with_freq(self, msg: DSCMessage, info: List[int], body_end: int):
        """Selective/Individual/All-ships call: TC1 + TC2 + freq."""
        # info[12]: TC2
        if body_end >= 13:
            msg.tc2_code = info[12]
            msg.tc2 = TELECOMMAND_2_CODES.get(info[12])

        # info[13..15]: subsequent communication frequency
        if body_end >= 16:
            f = _decode_frequency(info[13:16])
            if f:
                msg.frequency = f

    def _parse_distress(self, msg: DSCMessage, info: List[int], body_end: int):
        """Distress (112): self-ID, then nature + position + time directly.

        Distress format has no separate address; info[0..4] IS self-ID."""
        # Re-interpret: distress has self-ID in info[0..4], then immediately
        # nature at info[5], position at info[6..10], time at info[11..12]
        if body_end >= 6:
            msg.self_id = _decode_mmsi(info[0:5])
            msg.address = "ALL STATIONS"
            nature_code = info[5]
            if nature_code in DISTRESS_NATURE:
                msg.distress_nature_code = nature_code
                msg.distress_nature = DISTRESS_NATURE[nature_code]
        if body_end >= 11:
            pos = _decode_position(info[6:11])
            if pos:
                msg.position = pos
        if body_end >= 13:
            t = _decode_time(info[11:13])
            if t:
                msg.time_utc = t

    def parse_multiple(self, all_symbols: List[List[Tuple[int, bool]]]) -> List[DSCMessage]:
        """Parse each candidate stream; deduplicate by key fields."""
        messages = [self.parse(s) for s in all_symbols]
        seen = set()
        unique: List[DSCMessage] = []
        for m in messages:
            key = (m.format_code, m.self_id, m.address, m.distress_mmsi)
            if m.is_valid and key not in seen:
                seen.add(key)
                unique.append(m)
        return unique if unique else messages

    def extract_best_message(self, all_symbols: List[List[Tuple[int, bool]]]) -> Optional[DSCMessage]:
        """Return the highest-confidence valid message."""
        if not all_symbols:
            return None
        messages = [self.parse(s) for s in all_symbols]
        valid = [m for m in messages if m.is_valid]
        if valid:
            # Prefer messages with more extracted fields (richer = better sync)
            def score(m: DSCMessage):
                bonus = 0
                if m.distress_mmsi: bonus += 1
                if m.distress_nature: bonus += 1
                if m.position: bonus += 2
                if m.time_utc: bonus += 1
                if m.frequency: bonus += 1
                if m.ecc_valid: bonus += 2
                return (bonus, m.confidence)
            return max(valid, key=score)
        return max(messages, key=lambda m: m.confidence)

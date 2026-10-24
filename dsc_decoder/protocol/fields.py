"""
Field decoders for DSC message fields.

Decodes MMSI, position, time, frequency, and other DSC fields.
"""

from typing import List, Optional, Dict, Any
from .constants import (
    POSITION_QUADRANT, DISTRESS_NATURE, TELECOMMAND_1_CODES,
    CATEGORY_CODES, FORMAT_CODES
)


def decode_mmsi(symbols: List[int]) -> Optional[str]:
    """
    Decode MMSI (Maritime Mobile Service Identity) from symbols.

    MMSI is transmitted as 10 symbols encoding 9 digits (each pair of symbols = 2 digits).

    Args:
        symbols: List of 10 symbol values (0-9 typically)

    Returns:
        9-digit MMSI as string, or None if invalid
    """
    if len(symbols) < 10:
        return None

    try:
        mmsi = ""
        for i in range(0, 10, 2):
            # Each pair of symbols represents 2 digits
            # First symbol is tens, second is ones
            digit1 = symbols[i]
            digit2 = symbols[i + 1]

            if digit1 > 9 or digit2 > 9:
                # Invalid digit
                return None

            mmsi += str(digit1) + str(digit2)

        # MMSI should be 9 digits, but we got 10 digits
        # Take the first 9
        return mmsi[:9]

    except (IndexError, ValueError):
        return None


def decode_position(symbols: List[int]) -> Optional[Dict[str, Any]]:
    """
    Decode geographic position from symbols.

    Position is encoded as 10 symbols representing:
    - Quadrant (1 digit): 0=NE, 1=NW, 2=SE, 3=SW
    - Latitude degrees (2 digits)
    - Latitude minutes (4 digits, encoded as degrees*10 + minutes/10)
    - Longitude degrees (3 digits)
    - Longitude minutes (4 digits, encoded similarly)

    Actually, the encoding is simpler: just 14 digits total in pairs.

    Args:
        symbols: List of at least 10 symbols

    Returns:
        Dictionary with lat, lon, lat_str, lon_str, or None if invalid
    """
    if len(symbols) < 10:
        return None

    try:
        # Extract digits from symbols (each pair = 2 digits)
        digits = []
        for i in range(0, 10, 2):
            d1 = symbols[i]
            d2 = symbols[i + 1]

            if d1 > 9 or d2 > 9:
                return None

            digits.append(d1)
            digits.append(d2)

        # Parse position structure
        # Digits: Q DD MM.mm DDD MM.mm (14 total, but we have 10 symbols = 10 digits)
        # Actually: Q=1, Lat=4, Lon=5 = 10 digits

        quadrant = digits[0]
        lat_deg = digits[1] * 10 + digits[2]
        lat_min = digits[3] * 10 + digits[4]
        lon_deg = digits[5] * 100 + digits[6] * 10 + digits[7]
        lon_min = digits[8] * 10 + digits[9]

        # Validate ranges
        if quadrant > 3 or lat_deg > 90 or lat_min >= 60 or lon_deg > 180 or lon_min >= 60:
            return None

        # Convert to decimal degrees
        lat = lat_deg + lat_min / 60.0
        lon = lon_deg + lon_min / 60.0

        # Apply quadrant
        lat_dir, lon_dir = POSITION_QUADRANT.get(quadrant, ("N", "E"))

        if lat_dir == "S":
            lat = -lat
        if lon_dir == "W":
            lon = -lon

        # Format as strings
        lat_str = f"{abs(lat_deg)}°{lat_min:02d}.0'{lat_dir}"
        lon_str = f"{abs(lon_deg)}°{lon_min:02d}.0'{lon_dir}"

        return {
            'lat': lat,
            'lon': lon,
            'lat_str': lat_str,
            'lon_str': lon_str,
            'quadrant': quadrant
        }

    except (IndexError, ValueError, KeyError):
        return None


def decode_time(symbols: List[int]) -> Optional[str]:
    """
    Decode UTC time from symbols.

    Time is encoded as 4 symbols representing HHMM.

    Args:
        symbols: List of at least 4 symbols (2 pairs for HH:MM)

    Returns:
        Time string in format "HH:MM UTC", or None if invalid
    """
    if len(symbols) < 4:
        return None

    try:
        # Extract hour and minute
        hour = symbols[0] * 10 + symbols[1]
        minute = symbols[2] * 10 + symbols[3]

        # Validate
        if hour > 23 or minute > 59:
            return None

        return f"{hour:02d}:{minute:02d} UTC"

    except (IndexError, ValueError):
        return None


def decode_frequency(symbols: List[int]) -> Optional[Dict[str, Any]]:
    """
    Decode frequency or channel information.

    The encoding varies based on the first symbol which indicates the type.

    Args:
        symbols: List of symbols encoding frequency/channel

    Returns:
        Dictionary with 'type' and 'value', or None if invalid
    """
    if not symbols:
        return None

    try:
        first_symbol = symbols[0]

        # Common VHF channels
        if first_symbol in range(0, 28):  # VHF channels
            channel = first_symbol
            # Map to actual frequency if needed
            # For now, just return channel number
            return {
                'type': 'vhf_channel',
                'channel': channel,
                'description': f"VHF Channel {channel}"
            }

        # Frequency encoding (would need more symbols)
        # Simplified for now
        return {
            'type': 'frequency',
            'value': first_symbol,
            'description': f"Frequency code {first_symbol}"
        }

    except (IndexError, ValueError):
        return None


def decode_distress_nature(symbol: int) -> Optional[str]:
    """
    Decode nature of distress from symbol.

    Args:
        symbol: Single symbol value

    Returns:
        Description of distress nature, or None if unknown
    """
    return DISTRESS_NATURE.get(symbol, None)


def decode_category(symbols: List[int]) -> Optional[str]:
    """
    Decode message category (priority).

    Args:
        symbols: List of 2 symbols encoding category

    Returns:
        Category description, or None if unknown
    """
    if len(symbols) < 2:
        return None

    # Category is typically encoded in 2 symbols
    # First symbol is the category code
    category_code = symbols[0]

    return CATEGORY_CODES.get(category_code, None)


def decode_format_specifier(symbols: List[int]) -> Optional[str]:
    """
    Decode format specifier (message type).

    Args:
        symbols: List of 8 symbols (format specifier)

    Returns:
        Format description, or None if unknown
    """
    if len(symbols) < 8:
        return None

    # First symbol typically indicates the format type
    first_symbol = symbols[0]

    return FORMAT_CODES.get(first_symbol, None)


def decode_telecommand_1(symbol: int) -> Optional[str]:
    """
    Decode first telecommand.

    Args:
        symbol: Single symbol value

    Returns:
        Telecommand description, or None if unknown
    """
    return TELECOMMAND_1_CODES.get(symbol, None)


def symbols_to_digits(symbols: List[int]) -> Optional[str]:
    """
    Convert symbols to digit string.

    For symbols 0-9, this is a direct conversion.

    Args:
        symbols: List of symbol values

    Returns:
        String of digits, or None if any symbol > 9
    """
    try:
        if any(s > 9 for s in symbols):
            return None
        return ''.join(str(s) for s in symbols)
    except (TypeError, ValueError):
        return None

"""
DSC protocol constants.

Includes parity table, sync vectors, and other protocol-specific values
from ITU-R M.493 specification.
"""

# DSC signal parameters per ITU-R M.493-13 Annex 1 §1.1.5:
#   Binary "B" (1) corresponds to 1300 Hz (mark)
#   Binary "Y" (0) corresponds to 2100 Hz (space)
BAUD_RATE = 1200  # bits per second
F_MARK = 1300     # Hz (binary 1, M.493 "B")
F_SPACE = 2100    # Hz (binary 0, M.493 "Y")
F_CENTER = 1700   # Hz
F_SHIFT = 800     # Hz

# Symbol encoding
BITS_PER_SYMBOL = 10
INFO_BITS = 7
PARITY_BITS = 3

# Special symbols
SYMBOL_PREAMBLE = 125  # DX - marks start of message
SYMBOL_EOS = 127       # End of sequence
SYMBOL_ALL_SHIPS = 0   # Used in address field for broadcast

# Parity table: maps symbol value (0-127) to 10-bit on-air pattern
# per ITU-R M.493 (10-bit error-detecting code).
# Format: 7 information bits + 3 parity bits = 10 bits total
# Information bits are LSB first, parity bits are MSB first
PARITY_TABLE = {
    0: "0000000111", 1: "1000000110", 2: "0100000110", 3: "1100000101",
    4: "0010000110", 5: "1010000101", 6: "0110000101", 7: "1110000100",
    8: "0001000110", 9: "1001000101", 10: "0101000101", 11: "1101000100",
    12: "0011000101", 13: "1011000100", 14: "0111000100", 15: "1111000011",
    16: "0000100110", 17: "1000100101", 18: "0100100101", 19: "1100100100",
    20: "0010100101", 21: "1010100100", 22: "0110100100", 23: "1110100011",
    24: "0001100101", 25: "1001100100", 26: "0101100100", 27: "1101100011",
    28: "0011100100", 29: "1011100011", 30: "0111100011", 31: "1111100010",
    32: "0000010110", 33: "1000010101", 34: "0100010101", 35: "1100010100",
    36: "0010010101", 37: "1010010100", 38: "0110010100", 39: "1110010011",
    40: "0001010101", 41: "1001010100", 42: "0101010100", 43: "1101010011",
    44: "0011010100", 45: "1011010011", 46: "0111010011", 47: "1111010010",
    48: "0000110101", 49: "1000110100", 50: "0100110100", 51: "1100110011",
    52: "0010110100", 53: "1010110011", 54: "0110110011", 55: "1110110010",
    56: "0001110100", 57: "1001110011", 58: "0101110011", 59: "1101110010",
    60: "0011110011", 61: "1011110010", 62: "0111110010", 63: "1111110001",
    64: "0000001110", 65: "1000001101", 66: "0100001101", 67: "1100001100",
    68: "0010001101", 69: "1010001100", 70: "0110001100", 71: "1110001011",
    72: "0001001101", 73: "1001001100", 74: "0101001100", 75: "1101001011",
    76: "0011001100", 77: "1011001011", 78: "0111001011", 79: "1111001010",
    80: "0000101101", 81: "1000101100", 82: "0100101100", 83: "1100101011",
    84: "0010101100", 85: "1010101011", 86: "0110101011", 87: "1110101010",
    88: "0001101100", 89: "1001101011", 90: "0101101011", 91: "1101101010",
    92: "0011101011", 93: "1011101010", 94: "0111101010", 95: "1111101001",
    96: "0000011101", 97: "1000011100", 98: "0100011100", 99: "1100011011",
    100: "0010011100", 101: "1010011011", 102: "0110011011", 103: "1110011010",
    104: "0001011100", 105: "1001011011", 106: "0101011011", 107: "1101011010",
    108: "0011011011", 109: "1011011010", 110: "0111011010", 111: "1111011001",
    112: "0000111100", 113: "1000111011", 114: "0100111011", 115: "1100111010",
    116: "0010111011", 117: "1010111010", 118: "0110111010", 119: "1110111001",
    120: "0001111011", 121: "1001111010", 122: "0101111010", 123: "1101111001",
    124: "0011111010", 125: "1011111001", 126: "0111111001", 127: "1111111000"
}

# Inverted parity table for fast 10-bit pattern to symbol lookup
PARITY_TABLE_INV = {v: k for k, v in PARITY_TABLE.items()}

# Sync vectors used for detecting synchronization sequences
# (DRD and RRR patterns)
SYNC_VECTORS = [
    0x3FF, 0x3FE, 0x3FD, 0x3FC, 0x3FB, 0x3FA, 0x3F9, 0x3F8,
    0x3F7, 0x3F6, 0x3F5, 0x3F4, 0x3F3, 0x3F2, 0x3F1, 0x3F0
]

# Format specifier codes per ITU-R M.493 Table A1-1.
# Only these values are valid format specifiers; appears as 2 DX symbols
# (positions 12, 14 in the phasing block).
FORMAT_CODES = {
    102: "Geographic area call",
    112: "Distress alert",
    114: "Group call",
    116: "All ships",
    120: "Individual call",
    123: "Individual call (automatic service)",
}

# End-of-sequence markers (3 symbols at end of message)
SYMBOL_RQ = 117  # Acknowledgement requested
SYMBOL_BQ = 122  # Acknowledgement (response)
# SYMBOL_EOS = 127 already defined above (end of other sequences)

# Category codes (priority levels)
CATEGORY_CODES = {
    100: "Routine",
    108: "Safety",
    110: "Urgency",
    112: "Distress"
}

# First telecommand codes per ITU-R M.493 Table A1-2
TELECOMMAND_1_CODES = {
    100: "F3E/G3E All modes TP",
    101: "F3E/G3E Duplex TP",
    103: "Polling",
    104: "Unable to comply",
    105: "End of call",
    106: "Data",
    109: "J3E TP",
    110: "Distress acknowledgement",
    112: "Distress relay",
    113: "F1B/J2B TTY-FEC",
    115: "F1B/J2B TTY-ARQ",
    118: "Test",
    121: "Ship position or location and identification update",
    126: "No information",
}

# Second telecommand codes per ITU-R M.493 Table A1-2
TELECOMMAND_2_CODES = {
    100: "No reason given",
    101: "Congestion at maritime switching centre",
    102: "Busy",
    103: "Queue indication",
    104: "Station barred",
    105: "No operator available",
    106: "Operator temporarily unavailable",
    107: "Equipment disabled",
    108: "Unable to use proposed channel",
    109: "Unable to use proposed mode",
    110: "Ships and aircraft in distress",
    111: "Medical transports (Geneva Convention)",
    112: "Pay-phone/public call office",
    113: "Facsimile/data",
    126: "No information",
}

# Nature of distress codes
DISTRESS_NATURE = {
    100: "Fire/Explosion",
    101: "Flooding",
    102: "Collision",
    103: "Grounding",
    104: "Listing/Danger of capsizing",
    105: "Sinking",
    106: "Disabled and adrift",
    107: "Undesignated distress",
    108: "Abandoning ship",
    109: "Piracy/armed robbery attack",
    110: "Man overboard",
    112: "EPIRB emission",
}

# Position quadrant codes
POSITION_QUADRANT = {
    0: ("N", "E"),  # North, East
    1: ("N", "W"),  # North, West
    2: ("S", "E"),  # South, East
    3: ("S", "W"),  # South, West
}

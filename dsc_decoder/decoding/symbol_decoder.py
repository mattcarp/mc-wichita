"""
Symbol decoder for DSC messages.

Converts 10-bit patterns to 7-bit symbols with parity validation.
"""

from typing import Tuple, List
from ..protocol.constants import PARITY_TABLE, PARITY_TABLE_INV, BITS_PER_SYMBOL


class SymbolDecoder:
    """
    Decodes 10-bit patterns to DSC symbols (0-127) with parity checking.

    DSC uses a 10-bit encoding scheme:
    - 7 information bits (LSB first)
    - 3 parity bits (MSB first)

    The parity bits encode the count of zeros in the information bits.
    """

    def __init__(self):
        """Initialize symbol decoder with parity tables."""
        self.parity_table = PARITY_TABLE
        self.parity_table_inv = PARITY_TABLE_INV

    def decode_symbol(self, bits_10: str) -> Tuple[int, bool]:
        """
        Decode a 10-bit pattern to a symbol value.

        Args:
            bits_10: String of 10 bits (e.g., "0000000111")

        Returns:
            Tuple of (symbol_value, is_valid)
            - symbol_value: 0-127, or -1 if invalid
            - is_valid: True if parity check passed
        """
        if len(bits_10) != BITS_PER_SYMBOL:
            return -1, False

        # Look up symbol in inverted parity table
        if bits_10 in self.parity_table_inv:
            symbol = self.parity_table_inv[bits_10]

            # Verify parity
            info_bits = bits_10[:7]
            parity_bits = bits_10[7:]

            # Count zeros in information bits
            zero_count = info_bits.count('0')

            # Expected parity: MSB first representation of zero count.
            # format(n, '03b') already produces MSB first; do NOT reverse.
            expected_parity = format(zero_count, '03b')

            is_valid = (parity_bits == expected_parity)

            return symbol, is_valid
        else:
            # Unknown bit pattern
            return -1, False

    def decode_stream(self, bitstream: List[int], start_offset: int = 0) -> List[Tuple[int, bool]]:
        """
        Decode a bitstream to symbols starting at a given offset.

        Args:
            bitstream: List of bits (0 or 1)
            start_offset: Bit offset to start decoding (0-9 for alignment)

        Returns:
            List of tuples (symbol, is_valid)
        """
        symbols = []
        i = start_offset

        while i + BITS_PER_SYMBOL <= len(bitstream):
            # Extract 10 bits
            bits_10 = ''.join(str(bitstream[i + j]) for j in range(BITS_PER_SYMBOL))

            # Decode symbol
            symbol, is_valid = self.decode_symbol(bits_10)

            if symbol >= 0:  # Valid symbol found
                symbols.append((symbol, is_valid))

            i += BITS_PER_SYMBOL

        return symbols

    def find_best_alignment(self, bitstream: List[int], num_symbols: int = 20) -> Tuple[int, float]:
        """
        Find the best bit alignment by trying all 10 possible offsets.

        Args:
            bitstream: List of bits
            num_symbols: Number of symbols to test for alignment

        Returns:
            Tuple of (best_offset, validity_ratio)
            - best_offset: 0-9, the offset with most valid symbols
            - validity_ratio: Fraction of valid symbols at best offset
        """
        best_offset = 0
        best_valid_count = 0

        for offset in range(BITS_PER_SYMBOL):
            symbols = self.decode_stream(bitstream[offset:], start_offset=0)[:num_symbols]

            valid_count = sum(1 for _, is_valid in symbols if is_valid)

            if valid_count > best_valid_count:
                best_valid_count = valid_count
                best_offset = offset

        validity_ratio = best_valid_count / min(num_symbols, len(symbols)) if symbols else 0.0

        return best_offset, validity_ratio

    def validate_parity(self, bits_10: str) -> bool:
        """
        Check if parity bits are correct for given 10-bit pattern.

        Args:
            bits_10: String of 10 bits

        Returns:
            True if parity is valid
        """
        if len(bits_10) != BITS_PER_SYMBOL:
            return False

        info_bits = bits_10[:7]
        parity_bits = bits_10[7:]

        zero_count = info_bits.count('0')
        expected_parity = format(zero_count, '03b')

        return parity_bits == expected_parity

    def bits_to_string(self, bits: List[int]) -> str:
        """
        Convert list of bits to string for easier display.

        Args:
            bits: List of 0s and 1s

        Returns:
            String of bits
        """
        return ''.join(str(b) for b in bits)

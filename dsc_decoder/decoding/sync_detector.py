"""
Synchronization detector for DSC messages.

Finds phasing pattern and preamble to establish bit alignment.
"""

from typing import List, Tuple, Optional
from .symbol_decoder import SymbolDecoder
from ..protocol.constants import SYMBOL_PREAMBLE, BITS_PER_SYMBOL


class SyncDetector:
    """
    Detects synchronization in DSC bitstreams.

    DSC messages start with:
    1. Phasing (dot pattern): 100+ alternating bits
    2. Preamble: Symbol 125 repeated (DX sequence)
    """

    def __init__(self):
        """Initialize sync detector with symbol decoder."""
        self.symbol_decoder = SymbolDecoder()
        self.preamble_symbol = SYMBOL_PREAMBLE

    def find_phasing(self, bitstream: List[int], min_length: int = 80) -> Optional[int]:
        """
        Find phasing pattern (alternating bits).

        Args:
            bitstream: List of bits
            min_length: Minimum number of alternating bits (default 80)

        Returns:
            Index where phasing ends, or None if not found
        """
        max_alternating = 0
        max_position = 0
        current_alternating = 1  # Start with 1

        for i in range(1, len(bitstream)):
            # Check if current bit is different from previous
            if bitstream[i] != bitstream[i - 1]:
                current_alternating += 1
                if current_alternating > max_alternating:
                    max_alternating = current_alternating
                    max_position = i
            else:
                current_alternating = 1  # Reset

        if max_alternating >= min_length:
            return max_position + 1  # Position after phasing
        else:
            return None

    def find_preamble(self, bitstream: List[int], start_idx: int = 0,
                      search_length: int = 2000) -> Optional[Tuple[int, int]]:
        """
        Find best bit alignment by looking for valid DSC message structure.

        Looks for sequences that match DSC structure:
        - First symbol in range 100-127 (format codes)
        - No EOS (127) in first 20 symbols
        - Reasonable validity (>40%)

        Args:
            bitstream: List of bits
            start_idx: Index to start searching from
            search_length: Number of bits to search (default 2000)

        Returns:
            Tuple of (message_start_index, bit_phase_offset) or None
        """
        from ..protocol.constants import SYMBOL_EOS

        end_idx = min(start_idx + search_length, len(bitstream))

        best_offset = None
        best_start = None
        best_validity = 0.0

        # Try all 10 possible bit alignments
        for offset in range(BITS_PER_SYMBOL):
            i = start_idx + offset

            # Decode all symbols at this offset
            all_symbols = []
            while i + BITS_PER_SYMBOL <= end_idx:
                bits_10 = ''.join(str(bitstream[i + j]) for j in range(BITS_PER_SYMBOL))
                symbol, is_valid = self.symbol_decoder.decode_symbol(bits_10)

                if symbol >= 0:
                    all_symbols.append((i, symbol, is_valid))

                i += BITS_PER_SYMBOL

            if len(all_symbols) < 30:
                continue

            # Scan for valid message starts
            for idx in range(len(all_symbols) - 30):
                window = all_symbols[idx:idx+30]

                # Extract symbols and validity
                syms = [s for _, s, _ in window]
                vals = [v for _, _, v in window]

                # Check: first symbol should be format code (100-127)
                if syms[0] < 100:
                    continue

                # Check: no EOS in first 20 symbols
                if SYMBOL_EOS in syms[:20]:
                    continue

                # Check validity
                valid_count = sum(vals)
                validity = valid_count / len(window)

                if validity > best_validity and validity > 0.35:  # Lowered from 0.4
                    best_validity = validity
                    best_offset = offset
                    best_start = window[0][0]  # Bit position of first symbol

        if best_offset is not None:
            return best_start, best_offset

        return None

    def detect_sync(self, bitstream: List[int]) -> Optional[Tuple[int, int]]:
        """
        Complete synchronization detection.

        Finds both phasing and preamble.

        Args:
            bitstream: List of bits

        Returns:
            Tuple of (message_start_index, bit_phase_offset) or None
        """
        # First try to find phasing
        phasing_end = self.find_phasing(bitstream)

        if phasing_end is not None:
            # Search for preamble after phasing
            result = self.find_preamble(bitstream, start_idx=phasing_end)
            if result:
                return result

        # If phasing not found or preamble not found after phasing,
        # try searching entire bitstream for preamble
        result = self.find_preamble(bitstream, start_idx=0, search_length=len(bitstream))
        return result

    def detect_all_messages(self, bitstream: List[int]) -> List[Tuple[int, int]]:
        """
        Detect all messages in a bitstream.

        DSC typically transmits the same message 5 times.

        Args:
            bitstream: List of bits

        Returns:
            List of tuples (message_start_index, bit_phase_offset)
        """
        messages = []
        search_start = 0
        min_message_gap = 200  # Minimum bits between messages
        search_chunk = 5000  # Search in larger chunks (need room for all offsets)

        while search_start < len(bitstream) - 100:
            result = self.find_preamble(
                bitstream,
                start_idx=search_start,
                search_length=min(search_chunk, len(bitstream) - search_start)
            )

            if result:
                msg_start, offset = result
                messages.append((msg_start, offset))
                # Move search position forward past this message
                search_start = msg_start + min_message_gap
            else:
                # No message found in this chunk, move forward and keep searching
                # Use overlap to avoid missing messages at chunk boundaries
                search_start += search_chunk // 2

        return messages

    def get_sync_quality(self, bitstream: List[int], msg_start: int,
                        offset: int, num_symbols: int = 20) -> float:
        """
        Assess synchronization quality by checking parity of decoded symbols.

        Args:
            bitstream: List of bits
            msg_start: Message start index
            offset: Bit phase offset
            num_symbols: Number of symbols to check

        Returns:
            Quality score (0.0 to 1.0) based on valid parity ratio
        """
        symbols = self.symbol_decoder.decode_stream(
            bitstream[msg_start:],
            start_offset=0
        )[:num_symbols]

        if not symbols:
            return 0.0

        valid_count = sum(1 for _, is_valid in symbols if is_valid)
        return valid_count / len(symbols)

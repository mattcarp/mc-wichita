"""
Command-line interface for DSC decoder.

Main entry point for decoding DSC messages from audio files.
"""

import argparse
import sys
from pathlib import Path

from .audio.loader import load_audio, get_audio_info
from .demodulation.fsk_demod import FSKDemodulator
from .demodulation.band_detector import DSCBandDetector
from .decoding.symbol_decoder import SymbolDecoder
from .decoding.message_parser import MessageParser
from .output.formatter import OutputFormatter


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='GMDSS/DSC Decoder for VHF Radio Signals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s audio.wav
  %(prog)s audio.mp3 --debug --show-bitstream
  %(prog)s audio.wav --demod bandpass --output json
  %(prog)s audio.wav --language sv
        """
    )

    parser.add_argument(
        'audio_file',
        type=Path,
        help='Path to audio file (WAV, MP3, OGG, FLAC)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Show debug information'
    )

    parser.add_argument(
        '--show-bitstream',
        action='store_true',
        help='Display raw bitstream'
    )

    parser.add_argument(
        '--show-symbols',
        action='store_true',
        help='Display decoded symbols'
    )

    parser.add_argument(
        '--demod',
        choices=['goertzel', 'bandpass'],
        default='goertzel',
        help='Demodulation method (default: goertzel)'
    )

    parser.add_argument(
        '--output',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )

    parser.add_argument(
        '--language',
        choices=['en', 'sv'],
        default='en',
        help='Output language (default: en)'
    )

    parser.add_argument(
        '--all-messages',
        action='store_true',
        help='Show all detected messages (default: best message only)'
    )

    args = parser.parse_args()

    # Validate input file
    if not args.audio_file.exists():
        print(f"Error: File not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    try:
        # Print audio file info
        if args.debug:
            print(f"\nLoading audio file: {args.audio_file}")
            try:
                info = get_audio_info(str(args.audio_file))
                print(f"  Duration: {info['duration']:.2f}s")
                print(f"  Sample rate: {info['sample_rate']} Hz")
                print(f"  Channels: {info['channels']}")
                print(f"  Format: {info['format']}")
                print()
            except Exception as e:
                if args.debug:
                    print(f"  (Could not get audio info: {e})")

        # 1. Load audio
        if args.debug:
            print("Step 1: Loading and preprocessing audio...")

        samples, sample_rate = load_audio(str(args.audio_file), target_sr=22050)

        if args.debug:
            print(f"  Loaded {len(samples)} samples at {sample_rate} Hz")
            print(f"  Duration: {len(samples) / sample_rate:.2f}s")
            print()

        # 2. Auto-detect VHF vs HF
        if args.debug:
            print("Step 2: Auto-detecting signal band (VHF/HF)...")

        band_detector = DSCBandDetector()
        detected_params = band_detector.detect_band(samples, sample_rate)

        if args.debug:
            print(f"  Detected: {detected_params['name']}")
            print(f"  Baud rate: {detected_params['baud_rate']} baud")
            print(f"  Mark frequency: {detected_params['f_mark']} Hz")
            print(f"  Space frequency: {detected_params['f_space']} Hz")
            print(f"  Shift: {detected_params['shift']} Hz")
            print(f"  Confidence: {detected_params['detection_confidence']*100:.1f}%")
            if 'all_validities' in detected_params:
                print(f"  Symbol validities:")
                for band, val in detected_params['all_validities'].items():
                    print(f"    {band}: {val*100:.1f}%")
            print()

        # 3. Demodulate FSK with detected parameters
        if args.debug:
            print(f"Step 3: Demodulating FSK signal ({args.demod} method)...")

        demodulator = FSKDemodulator(
            method=args.demod,
            baud_rate=detected_params['baud_rate'],
            f_space=detected_params['f_space'],
            f_mark=detected_params['f_mark']
        )
        bitstream = demodulator.demodulate(samples, sample_rate)

        if args.debug:
            print(f"  Extracted {len(bitstream)} bits")
            signal_strength = demodulator.get_signal_strength(samples[:1000], sample_rate)
            print(f"  Signal strength - Space: {signal_strength['space']:.2f}, " +
                  f"Mark: {signal_strength['mark']:.2f}")
            print()

        if args.show_bitstream:
            formatter = OutputFormatter(language=args.language)
            print(formatter.format_bitstream(bitstream.tolist()))
            print()

        # 4. Decode symbols at each bit offset and slice into per-phasing windows
        if args.debug:
            print("Step 4: Decoding symbols at all bit offsets and finding phasing...")

        from .decoding.message_parser import find_all_phasings, PHASING_LEN

        symbol_decoder = SymbolDecoder()
        all_decoded_symbols = []
        bits_list = bitstream.tolist()

        for offset in range(10):
            stream = symbol_decoder.decode_stream(bits_list, start_offset=offset)
            syms_only = [s for s, _ in stream]
            for ph_idx in find_all_phasings(syms_only):
                # Window spans phasing block + ~50 symbols of message body
                window = stream[ph_idx: ph_idx + PHASING_LEN + 100]
                if len(window) >= 25:
                    all_decoded_symbols.append(window)
                    if args.debug:
                        valid_count = sum(1 for _, v in window if v)
                        print(f"  Offset {offset}, phasing@{ph_idx}: " +
                              f"{len(window)} symbols, {valid_count} valid " +
                              f"({valid_count / len(window) * 100:.1f}%)")

        if not all_decoded_symbols:
            print("No DSC messages found in the audio file.")
            print("\nTips:")
            print(f"  - Detected signal type: {detected_params['name']}")
            print("  - Try the alternative demodulation method: --demod bandpass")
            print("  - Use --debug to see detailed processing information")
            sys.exit(0)

        if args.debug:
            print(f"  Total {len(all_decoded_symbols)} candidate window(s)")
            print()

        if not all_decoded_symbols:
            print("No valid symbols decoded.")
            sys.exit(0)

        if args.show_symbols:
            formatter = OutputFormatter(language=args.language)
            for i, symbols in enumerate(all_decoded_symbols, 1):
                print(f"\n--- Message {i} symbols ---")
                print(formatter.format_symbols(symbols))
                print()

        # 6. Parse messages
        if args.debug:
            print("Step 6: Parsing messages...")

        message_parser = MessageParser()

        if args.all_messages:
            messages = message_parser.parse_multiple(all_decoded_symbols)
        else:
            best_message = message_parser.extract_best_message(all_decoded_symbols)
            messages = [best_message] if best_message else []

        if args.debug:
            print(f"  Parsed {len(messages)} message(s)")
            print()

        # 7. Output results
        formatter = OutputFormatter(language=args.language)

        if args.output == 'json':
            import json
            if len(messages) == 1:
                print(formatter.format_json(messages[0]))
            else:
                output = [msg.to_dict() for msg in messages]
                print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            if len(messages) == 1:
                print(formatter.format_message(messages[0], show_debug=args.debug))
            else:
                print(formatter.format_multiple_messages(messages))

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        if args.debug:
            raise
        else:
            print(f"\nError: {e}", file=sys.stderr)
            print("\nRun with --debug for detailed error information", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()

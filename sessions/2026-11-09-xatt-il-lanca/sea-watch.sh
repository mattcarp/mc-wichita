#!/usr/bin/env bash
# Wichita sea watch — receive only, never transmits.
# Usage:
#   ./sea-watch.sh ais            # AIS decode on an SDR + live map at http://127.0.0.1:8110
#   ./sea-watch.sh voice [FREQ]   # record marine voice in 5-min WAV chunks (default CH16 156.800M)
#   ./sea-watch.sh adsb           # ADS-B 1090 map-free dump1090 (needs the HackRF, sees planes overhead)
# Options: DEV=<serial-or-index> picks an SDR for the ais/voice modes.
# Stop any mode with Ctrl-C. Everything lands in one timestamped folder.

set -uo pipefail
BIN="$HOME/.local/bin/ais-catcher"
OUT="$HOME/wichita-captures/sea-$(date +%Y%m%d-%H%M)"
mkdir -p "$OUT" || exit 1
NOTES="$OUT/notes.txt"
[ -f "$NOTES" ] || printf "# session notes %s\n# HH:MM:SS <what>\n" "$(date +%Y-%m-%d\ %H:%M)" > "$NOTES"
echo "notes: $NOTES"
DEVARG=()
[ -n "${DEV:-}" ] && DEVARG=(-d "$DEV")

case "${1:-help}" in
  ais)
    command -v "$BIN" >/dev/null || { echo "ais-catcher missing at $BIN"; exit 1; }
    echo "AIS -> http://127.0.0.1:8110   log: $OUT/ais.nmea"
    exec "$BIN" -s 1536000 -c AB -N 8110 -M TD -q -f "$OUT/ais.nmea" "${DEVARG[@]}"
    ;;
  voice)
    FREQ="${2:-156.800M}"
    echo "recording $FREQ to $OUT in 5-minute chunks (Ctrl-C to stop)"
    i=0
    while :; do
      i=$((i+1))
      f=$(printf "%s/CH_%s-%03d.wav" "$OUT" "${FREQ//./_}" "$i")
      echo "[$(date +%H:%M:%S)] $f"
      rtl_fm -f "$FREQ" -M fm -s 24k -l 0 -E dc -g 40 - 2>/dev/null \
        | sox -q -t raw -r 24k -e s -b 16 -c 1 - "$f" trim 0 300
    done
    ;;
  adsb)
    echo "ADS-B via HackRF at 1090 MHz. Ctrl-C to stop. Log: $OUT/aircraft.log"
    hackrf_transfer -r - -f 1090000000 -s 2000000 -g 32 -a 0 2>/dev/null \
      | dump1090 --ifile - --iformat UC8 --modeac 2>/dev/null \
      | tee -a "$OUT/aircraft.log"
    ;;
  *)
    sed -n '2,9p' "$0"
    ;;
esac

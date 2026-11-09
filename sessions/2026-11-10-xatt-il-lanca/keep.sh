#!/usr/bin/env bash
# Fold a finished sea session into the repo without moving or re-encoding the audio.
# Usage: ./keep.sh [session-folder-in-~/wichita-captures]
# With no argument it takes the newest ~/wichita-captures/sea-* folder.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-$(ls -dt "$HOME"/wichita-captures/sea-* 2>/dev/null | head -1)}"
[ -n "${SRC:-}" ] && [ -d "$SRC" ] || { echo "no session folder found"; exit 1; }

mkdir -p "$HERE/data"
cp -n "$SRC"/notes.txt "$HERE/data/" 2>/dev/null || true
cp -n "$SRC"/ais.nmea "$HERE/data/" 2>/dev/null || true
cp -n "$SRC"/aircraft.log "$HERE/data/" 2>/dev/null || true

MAN="$HERE/data/audio-manifest.tsv"
: > "$MAN"
printf "file\tsize_bytes\tsha256\n" >> "$MAN"
while IFS= read -r f; do
  printf "%s\t%s\t%s\n" "$(basename "$f")" "$(stat -f%z "$f")" \
    "$(shasum -a 256 "$f" | cut -d' ' -f1)" >> "$MAN"
done < <(find "$SRC" -name '*.wav' | sort)

echo "Session: $SRC"
echo "Folded into: $HERE/data"
echo
echo "Audio stays put. Review these:"
find "$SRC" -name '*.wav' -size +20k | sort
echo
echo "Next: pick clips, name kept ones REAL_RTL_CAPTURE_<label>_<freq>MHz_<YYYYMMDD>_<HHMMSS>.wav,"
echo "then per clip: python3 capture_provenance.py write <clip> --frequency-mhz <mhz> --status genuine"

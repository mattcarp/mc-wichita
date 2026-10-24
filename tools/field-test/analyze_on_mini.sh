#!/bin/bash
# Channel + LoRa analysis for a capture folder made on a computer without numpy (e.g. the Air).
# Ships only what chan.py/lora.py read (first 4,915,200 bytes of each narrowband cs8, plus the
# whole LORA868 file) to the Mini's /tmp, runs the baseline scripts there, then rewrites
# SUMMARY.md and COMPARE.md locally. Raw captures on this computer are untouched.
# Usage: analyze_on_mini.sh <capture-dir> [--baseline DIR]
HERE="$(cd "$(dirname "$0")" && pwd)"
D="$(cd "$1" && pwd)" || exit 2; shift
BASE="$HERE/baseline-2026-10-24-shaft"; [ "$1" = "--baseline" ] && BASE="$2"
N=$(basename "$D"); R="/tmp/wichita-analysis-$N"
MINI="${WICHITA_MINI:-mini}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cd "$D" || exit 1
for f in *_ctr*.cs8; do [ -e "$f" ] && head -c 4915200 "$f" > "$TMP/$f"; done
echo "sending $(du -sh "$TMP" | cut -f1) of channel heads$(ls *_LORA868_*.cs8 >/dev/null 2>&1 && echo ' + LORA868 file') to $MINI:$R ..."
ssh -o ConnectTimeout=15 "$MINI" "mkdir -p $R" || { echo "Mini not reachable"; exit 3; }
( tar cf - -C "$TMP" . ; ) | ssh "$MINI" "tar xf - -C $R" || exit 4
ls *_LORA868_*.cs8 >/dev/null 2>&1 && { tar cf - *_LORA868_*.cs8 | ssh "$MINI" "tar xf - -C $R" || exit 4; }
RP='export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH; python3'
CH=$(ssh "$MINI" "$RP - $R" < "$HERE/chan.py" | grep -vE '^(LORA868|ISM433) ') || exit 5
LO=""; ls *_LORA868_*.cs8 >/dev/null 2>&1 && LO=$(ssh "$MINI" "$RP - $R" < "$HERE/lora.py")
python3 - "$D/SUMMARY.md" "$CH" "$LO" <<'PY'
import sys
p, ch, lo = sys.argv[1:4]
s = open(p).read()
cut = s.find('\n## Channels')
s = (s[:cut] if cut >= 0 else s.rstrip('\n')) + '\n\n## Channels (SNR within 8 kHz of target vs. nearby noise; active = share of frames over 6 dB; computed on the Mini)\n' + ch.strip() + '\n'
if lo.strip(): s += '\n## LoRa 868 (centred 868.85)\n' + lo.strip() + '\n'
open(p, 'w').write(s)
PY
cat "$D/SUMMARY.md"
[ -d "$BASE" ] && python3 "$HERE/compare.py" "$BASE" "$D" >/dev/null && echo "comparison written to $D/COMPARE.md"
echo "(copies left on the Mini in $R)"

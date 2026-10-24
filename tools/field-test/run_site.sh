#!/bin/bash
# Wichita field test: same receive-only plan as the 24 Oct 2026 shaft baseline (baseline.sh).
# Usage: run_site.sh <site-name> [--quick] [--baseline DIR]
#   full  ~24 min, ~5.8 GB   |   --quick  ~5 min, ~1.1 GB
# Receive only. Never TETRA (380-400 MHz), GSM/LTE/5G or DECT.
# Ctrl-C once: stop the current recording, keep everything captured, write the summary + compare.
# Ctrl-C twice: quit immediately.
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
HERE="$(cd "$(dirname "$0")" && pwd)"
SITE=""; QUICK=0; BASE="$HERE/baseline-2026-10-24-shaft"
while [ $# -gt 0 ]; do
  case "$1" in
    --quick) QUICK=1 ;;
    --baseline) shift; BASE="$1" ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) SITE="$1" ;;
  esac; shift
done
[ -z "$SITE" ] && { echo "usage: $0 <site-name> [--quick] [--baseline DIR]"; exit 2; }
SITE=$(echo "$SITE" | tr ' A-Z' '-a-z' | tr -cd 'a-z0-9._-')
[ $QUICK = 1 ] && SITE="$SITE-quick"

# --- settings: identical to the baseline ---
FS=2000000; LNA=32; VGA=20; AMP=0; OFF=250000

# --- plan: name:freqHz:seconds  (ctr = freq + 250 kHz, except LORA868/ISM433 centred exactly) ---
SWEEPS="118:137 156:163 860:870 430:447"
FULL="FM92.7:92700000:20
CH16:156800000:30 CH69:156475000:30 CH12:156600000:30 CH14:156700000:30 CH10:156500000:30 CH09:156450000:30 CH11:156550000:30 CH06:156300000:30 CH13:156650000:30 CH72:156625000:30 CH77:156875000:30 AIS1:161975000:30 AIS2:162025000:30
TWR1:135105000:30 TWR2:133905000:30 APP1:128155000:30 APP2:118355000:30 GND:121605000:30 ATIS1:127005000:30 ATIS2:127405000:30 GUARD:121500000:30 CTL1:127525000:30 CTL2:122775000:30 CTL3:130975000:30
LORA868:868850000:300 ISM433:433920000:60
R2m1:145625000:30 R2m2:145700000:30 R2m3:145750000:30 R2m4:145475000:30 R70a:430875000:30 R70b:430925000:30 R70c:433175000:30 R70d:438650000:30 PMR446:446100000:30 CB27:27185000:30
CH70:156525000:30"
QUICKPLAN="AIS1:161975000:30 AIS2:162025000:30 CH16:156800000:30 CH70:156525000:30 ATIS1:127005000:30 ATIS2:127405000:30 TWR1:135105000:30 FM92.7:92700000:20 CH12:156600000:30"
if [ $QUICK = 1 ]; then PLAN="$QUICKPLAN"; else PLAN="$FULL"; fi
PLAN=$(echo $PLAN)   # flatten

# exclusion guard: refuse 380-400 MHz (TETRA) and the cellular/DECT bands outright
for x in $PLAN; do f=$(echo "$x" | cut -d: -f2)
  if [ $f -ge 380000000 -a $f -le 400000000 ] || [ $f -ge 700000000 -a $f -le 860000000 ] || [ $f -ge 880000000 ]; then
    echo "REFUSED: $x is in an excluded band"; exit 3; fi; done

NREC=0; TOTAL_S=0; BYTES=0
for x in $PLAN; do s=$(echo "$x" | cut -d: -f3); NREC=$((NREC+1)); TOTAL_S=$((TOTAL_S+s)); BYTES=$((BYTES + s*FS*2)); done
NEED_GB=$(( BYTES/1000000000 + 3 ))

# --- pre-flight ---
FREE_GB=$(df -k "$HOME" | awk 'NR==2{print int($4/1000000)}')
echo "Wichita field test: $SITE   plan: $NREC recordings + 4 sweeps, ~$(( (TOTAL_S+NREC+10)/60 )) min, ~$(( BYTES/1000000 )) MB"
echo "disk free: ${FREE_GB} GB (need ${NEED_GB} GB)"
[ "$FREE_GB" -lt "$NEED_GB" ] && { echo "NOT ENOUGH DISK - stopping before anything is recorded"; exit 4; }
if ! hackrf_info 2>/dev/null | grep -q "Serial number"; then
  echo "No HackRF found. Plug it in (and close SDR++/PortaPack apps using it), then re-run."; exit 5; fi
hackrf_info 2>/dev/null | grep -E "Serial number|Firmware Version" | sed 's/^/  /'

D="$HOME/wichita-captures/$(date +%F)-$SITE"
[ -e "$D" ] && D="$D-$(date +%H%M)"
mkdir -p "$D"; cd "$D" || exit 1
LOG="$D/progress.log"; T0=$(date +%s)
echo "start $(date +%T)" > "$LOG"
{ echo "site=$SITE quick=$QUICK host=$(hostname) fs=$FS lna=$LNA vga=$VGA amp=$AMP offset=$OFF"; hackrf_info 2>/dev/null | grep -E "Serial|Firmware|Board ID"; } > "$D/run-info.txt"
echo "writing to $D"

# --- once-a-minute status ticker ---
( while sleep 60; do
    el=$(( $(date +%s) - T0 )); last=$(tail -1 "$LOG" 2>/dev/null)
    done_n=$(grep -c '^rec ' "$LOG" 2>/dev/null)
    left=$(( TOTAL_S + NREC + 10 - el )); [ $left -lt 0 ] && left=0
    fg=$(df -k "$HOME" | awk 'NR==2{print int($4/1000000)}')
    printf '[%s] %2dm elapsed | %d/%d recordings | ~%dm left | %s GB free | last: %s\n' "$(date +%H:%M)" $((el/60)) "$done_n" $NREC $(( (left+59)/60 )) "$fg" "$last"
  done ) &
TICK=$!

STOP=0; CHILD=""
onint() {
  if [ $STOP = 1 ]; then echo; echo "quit now"; kill $CHILD $TICK 2>/dev/null; exit 130; fi
  STOP=1; echo; echo "Ctrl-C: stopping after this step, keeping all captures (Ctrl-C again to quit now)"
  echo "INTERRUPTED $(date +%T)" >> "$LOG"; [ -n "$CHILD" ] && kill -TERM $CHILD 2>/dev/null
}
trap onint INT
trap 'kill $TICK 2>/dev/null' EXIT
run() { "$@" >/dev/null 2>&1 & CHILD=$!; wait $CHILD; local rc=$?; while kill -0 $CHILD 2>/dev/null; do wait $CHILD; rc=$?; done; CHILD=""; return $rc; }

# 1. power sweeps (identical to baseline)
for r in $SWEEPS; do [ $STOP = 1 ] && break
  n=${r/:/-}
  run hackrf_sweep -f $r -w 25000 -l $LNA -g $VGA -a $AMP -N 20 -r sweep_${n}MHz.csv
  echo "sweep $n done $(date +%T)" >> "$LOG"
done
echo "[$(date +%H:%M)] sweeps done, starting $NREC recordings"

# 2. recordings
i=0
for x in $PLAN; do [ $STOP = 1 ] && break
  name=$(echo "$x" | cut -d: -f1); f=$(echo "$x" | cut -d: -f2); s=$(echo "$x" | cut -d: -f3)
  i=$((i+1))
  case $name in
    LORA868|ISM433) c=$f; fn="$(date +%H%M%S)_${name}_${f}Hz.cs8" ;;
    *) c=$((f+OFF)); fn="$(date +%H%M%S)_${name}_${f}Hz_ctr${c}.cs8" ;;
  esac
  run hackrf_transfer -r "$fn" -f $c -s $FS -l $LNA -g $VGA -a $AMP -n $((FS*s))
  got=$(wc -c < "$fn" 2>/dev/null | tr -d " "); got=${got:-0}
  want=$((FS*s*2))
  if [ "$got" -ge "$want" ]; then echo "rec $name $f done $(date +%T)" >> "$LOG"
  elif [ $STOP = 1 ]; then echo "rec $name $f PARTIAL (stopped by Ctrl-C, $got of $want bytes) $(date +%T)" >> "$LOG"
  else echo "rec $name $f SHORT ($got of $want bytes) $(date +%T)" >> "$LOG"; echo "  ! $name came back short - is the HackRF still connected?"; fi
done
[ $STOP = 0 ] && echo "ALL DONE $(date +%T)" >> "$LOG"
kill $TICK 2>/dev/null; trap - INT
echo "[$(date +%H:%M)] recording finished ($(du -sh "$D" | cut -f1)). Analysing..."

# 3. analysis (same methods as the baseline) -> SUMMARY.md, then COMPARE.md
PY=""
for c in "$WICHITA_PY" python3 /usr/bin/python3 /opt/homebrew/bin/python3 "$HOME"/.venv/bin/python "$HOME"/venv/bin/python; do
  [ -n "$c" ] && "$c" -c 'import numpy' >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$WICHITA_NO_NUMPY" ] && PY=""   # testing hook
{
  echo "# Wichita field test: $SITE ($(date +%F), $(head -1 "$LOG" | cut -d' ' -f2)-$(date +%H:%M) $(date +%Z))"
  echo; echo "HackRF on $(hostname -s). ${FS} sps, LNA $LNA, VGA $VGA, amp off. Narrowband recordings tuned 250 kHz above the target. Receive-only."
  echo; echo "## Sweeps (peak above the median floor)"; python3 "$HERE/peaks.py" "$D" 2>&1
} > "$D/SUMMARY.md"
if [ -n "$PY" ]; then
  { echo; echo "## Channels (SNR within 8 kHz of target vs. nearby noise; active = share of frames over 6 dB)"
    "$PY" "$HERE/chan.py" "$D" 2>&1 | grep -vE '^(LORA868|ISM433) '
    if ls "$D"/*_LORA868_*.cs8 >/dev/null 2>&1; then echo; echo "## LoRa 868 (centred 868.85)"; "$PY" "$HERE/lora.py" "$D" 2>&1; fi
  } >> "$D/SUMMARY.md"
else
  { echo; echo "## Channels"; echo "Pending: no numpy on this computer. Run: bash $HERE/analyze_on_mini.sh $D"; } >> "$D/SUMMARY.md"
fi
cat "$D/SUMMARY.md"
if [ -d "$BASE" ]; then python3 "$HERE/compare.py" "$BASE" "$D" >/dev/null && echo "comparison written to $D/COMPARE.md"
else echo "baseline folder $BASE not found - run: python3 $HERE/compare.py <baseline-dir> $D"; fi
[ -z "$PY" ] && echo ">>> Channel numbers need numpy. Back on the home network run:  bash $HERE/analyze_on_mini.sh $D"
echo "DONE. Captures: $D"

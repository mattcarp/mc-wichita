#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
D=~/wichita-captures/2026-10-24-baseline-shaft
mkdir -p $D; cd $D
LOG=$D/progress.log
echo "start $(date +%T)" > $LOG
# 1. quick power sweeps (receive-only)
for r in 118:137 156:163 860:870 430:447; do
  n=${r/:/-}
  hackrf_sweep -f $r -w 25000 -l 32 -g 20 -a 0 -N 20 -r sweep_${n}MHz.csv >/dev/null 2>&1
  echo "sweep $n done $(date +%T)" >> $LOG
done
rec() { # name freqHz seconds
  local f=$2 s=$3 c=$(( $2 + 250000 ))
  local fn="$(date +%H%M%S)_${1}_${f}Hz_ctr${c}.cs8"
  hackrf_transfer -r $fn -f $c -s 2000000 -l 32 -g 20 -a 0 -n $(( 2000000 * s )) >/dev/null 2>&1
  echo "rec $1 $f done $(date +%T)" >> $LOG
}
rec FM92.7 92700000 20
for x in CH16:156800000 CH69:156475000 CH12:156600000 CH14:156700000 CH10:156500000 CH09:156450000 CH11:156550000 CH06:156300000 CH13:156650000 CH72:156625000 CH77:156875000 AIS1:161975000 AIS2:162025000; do rec ${x%%:*} ${x##*:} 30; done
for x in TWR1:135105000 TWR2:133905000 APP1:128155000 APP2:118355000 GND:121605000 ATIS1:127005000 ATIS2:127405000 GUARD:121500000 CTL1:127525000 CTL2:122775000 CTL3:130975000; do rec ${x%%:*} ${x##*:} 30; done
# Meshtastic: centre exactly 868.85 MHz, 5 min
fn="$(date +%H%M%S)_LORA868_868850000Hz.cs8"; hackrf_transfer -r $fn -f 868850000 -s 2000000 -l 32 -g 20 -a 0 -n $((2000000*300)) >/dev/null 2>&1; echo "rec LORA868 done $(date +%T)" >> $LOG
fn="$(date +%H%M%S)_ISM433_433920000Hz.cs8"; hackrf_transfer -r $fn -f 433920000 -s 2000000 -l 32 -g 20 -a 0 -n $((2000000*60)) >/dev/null 2>&1; echo "rec ISM433 done $(date +%T)" >> $LOG
for x in R2m1:145625000 R2m2:145700000 R2m3:145750000 R2m4:145475000 R70a:430875000 R70b:430925000 R70c:433175000 R70d:438650000 PMR446:446100000 CB27:27185000; do rec ${x%%:*} ${x##*:} 30; done
echo "ALL DONE $(date +%T)" >> $LOG

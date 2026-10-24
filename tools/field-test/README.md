# Wichita field test (receive-only)

Like-for-like RF site survey against the 24 Oct 2026 shaft baseline (50 Archbishop St, 15:36-15:59 Malta time).

| File | What |
|---|---|
| `baseline.sh`, `peaks.py`, `chan.py`, `lora.py` | The exact scripts used for the baseline (copied from the Mini's /tmp). |
| `baseline-2026-10-24-shaft/` | Baseline BASELINE.md, progress.log and the four raw sweep CSVs (the 5.6 GB of cs8 stay on the Mini in ~/wichita-captures/2026-10-24-baseline-shaft/). |
| `run_site.sh` | One-command field run, same plan/settings/offsets as the baseline. |
| `analyze_on_mini.sh` | Channel/LoRa analysis on the Mini for runs made on a computer without numpy. |
| `compare.py` | Per-channel and sweep comparison of two capture folders -> COMPARE.md. |

## Run on site (HackRF plugged into the laptop)

    bash ~/wichita-field/run_site.sh st-georges-square           # full, ~24 min, ~5.8 GB
    bash ~/wichita-field/run_site.sh st-georges-square --quick   # ~5 min, ~1.1 GB

- Settings: 2 Msps, LNA 32, VGA 20, amp off; narrowband recordings centred 250 kHz above target (LoRa 868.85 and ISM 433.92 centred exactly).
- Full plan = baseline plan in the same order, plus CH70 (156.525, DSC) appended at the end (no baseline value for CH70).
- Quick = 4 sweeps + AIS1, AIS2, CH16, CH70, ATIS1, ATIS2, TWR1 (135.105), FM 92.7, CH12.
- Checks free disk and that a HackRF is attached before recording. Status line every minute.
- Ctrl-C once: stops the current recording, keeps everything, still writes SUMMARY.md + COMPARE.md. Ctrl-C twice: quit now.
- Output: `~/wichita-captures/<YYYY-MM-DD>-<site>[-quick]/` with raw cs8, sweep CSVs, progress.log, run-info.txt, SUMMARY.md, COMPARE.md.
- Channel analysis (`chan.py`, `lora.py`) needs numpy; sweep analysis and compare.py are pure Python. The Air has no numpy, so on the Air the run records everything, writes the sweep part of SUMMARY.md/COMPARE.md, and tells you to run `bash ~/wichita-field/analyze_on_mini.sh <capture-dir>` once the Mini is reachable. That ships only the bytes chan.py reads (~4.9 MB per channel) plus the LoRa file (1.2 GB, full run only) to the Mini's /tmp, runs the same scripts there, and fills in the channel tables and COMPARE.md. Nothing is installed.
- Method note (kept identical for comparability): `chan.py` reads the first 600 x 4096 samples (~1.2 s) of each recording.

Exclusions are hard-coded: the script refuses 380-400 MHz (TETRA) and cellular/DECT ranges. Receive only; nothing here transmits.

## Compare any two runs

    python3 compare.py <baseline-dir> <new-dir>     # writes <new-dir>/COMPARE.md

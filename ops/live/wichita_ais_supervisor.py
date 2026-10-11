#!/usr/bin/env python3
"""Receive-only AIS supervisor for Wichita (Mac Mini).

Runs AIS-catcher on the SDRplay RSPdx-R2 via SoapySDR, Antenna A, Bias-T explicitly false.
Bias-T guard: AIS-catcher prints its in-session readback (PROBE on). If the readback does
not show biasT_ctrl=false within GUARD_SECONDS, or ever shows biasT_ctrl=true, AIS-catcher
is killed, a BIAST_ABORT marker is written and this supervisor exits 0 (launchd will not
restart it: KeepAlive SuccessfulExit=false).
Persistence: every decoded message (AIS-catcher -o 5 JSON Full, one object per line) is
appended to ~/wichita/live/ais/YYYY/ais-YYYY-MM-DD.jsonl (UTC date), flushed per line.
A write failure exits non-zero (launchd restarts) rather than dropping data silently.
Nothing here transmits. Stdlib only.
"""
import os, re, shutil, signal, subprocess, sys, threading, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
BIN = os.path.join(HOME, "wichita/src/AIS-catcher/build/AIS-catcher")
OUT_DIR = os.path.join(HOME, "wichita/live/ais")
STATE_DIR = os.path.join(OUT_DIR, "state")
LOG = os.path.join(HOME, "wichita/logs/ais.catcher.log")
MARKER = os.path.join(OUT_DIR, "BIAST_ABORT")
GUARD_SECONDS = 30
DISK_WARN_GB = 20

CMD = [BIN,
       "-d", "SCH0-sdrplay", "-s", "2304000",
       "-gu", "DEVICE", "driver=sdrplay,serial=2403090170",
       "ANTENNA", "Antenna A",
       "SETTING", "biasT_ctrl=false,rfnotch_ctrl=true,dabnotch_ctrl=false,iqcorr_ctrl=true",
       "AGC", "off", "GAIN", "IFGR=35,RFGR=4", "PROBE", "on",
       "-M", "DT", "-o", "5", "-v", "60",
       "-N", "8100", "IP_BIND", "127.0.0.1", "REALTIME", "on",
       "BACKUP", "10", "FILE", os.path.join(STATE_DIR, "aiscatcher-backup.bin")]


def log(msg):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"{stamp} [supervisor] {msg}\n")


def main():
    if os.path.exists(MARKER):
        log("BIAST_ABORT marker present; refusing to start. Investigate, then delete the marker.")
        return 0
    os.makedirs(STATE_DIR, exist_ok=True)
    log("starting: " + " ".join(CMD))
    proc = subprocess.Popen(CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, text=True)
    verified = threading.Event()
    abort = threading.Event()

    def stop_child():
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    def read_err():
        with open(LOG, "a") as f:
            for line in proc.stderr:
                f.write(line); f.flush()
                if "SETTING" in line and "biasT_ctrl=" in line:
                    m = re.search(r"biasT_ctrl=(\S+)", line)
                    if m and m.group(1) == "false":
                        verified.set()
                        log("Bias-T readback verified false: " + line.strip())
                    else:
                        abort.set()
                        log("Bias-T readback NOT false: " + line.strip())
                        stop_child()

    t = threading.Thread(target=read_err, daemon=True); t.start()

    def guard():
        if not verified.wait(GUARD_SECONDS):
            abort.set()
            log(f"no Bias-T readback within {GUARD_SECONDS}s; stopping")
            stop_child()
    threading.Thread(target=guard, daemon=True).start()

    def on_term(signum, frame):
        log(f"signal {signum}; stopping AIS-catcher")
        stop_child()
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    cur_day, fh, last_disk = None, None, 0
    try:
        for line in proc.stdout:
            if not line.strip():
                continue
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if day != cur_day:
                if fh: fh.close()
                d = os.path.join(OUT_DIR, day[:4]); os.makedirs(d, exist_ok=True)
                fh = open(os.path.join(d, f"ais-{day}.jsonl"), "a")
                cur_day = day
            fh.write(line if line.endswith("\n") else line + "\n"); fh.flush()
            now = time.time()
            if now - last_disk > 3600:
                last_disk = now
                free = shutil.disk_usage(OUT_DIR).free / 1e9
                log(f"disk free {free:.1f} GB")
                if free < DISK_WARN_GB:
                    log(f"WARNING disk free below {DISK_WARN_GB} GB; data still being written, tell Mattie")
    except OSError as e:
        log(f"write failure {e!r}; exiting non-zero so launchd restarts (no silent drop)")
        stop_child(); return 3
    finally:
        if fh: fh.close()
    rc = proc.wait()
    if abort.is_set():
        with open(MARKER, "w") as m:
            m.write(datetime.now(timezone.utc).isoformat() + " Bias-T not verified false; AIS supervisor halted\n")
        log("halted: Bias-T not verified; marker written; not restarting")
        return 0
    log(f"AIS-catcher exited rc={rc}")
    return 1 if rc == 0 else rc


if __name__ == "__main__":
    sys.exit(main())

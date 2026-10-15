# Ground voice receiver on the Mini (marine ch16)

Receive-only. RTL-SDR Blog V4 -> rtl_airband (NFM 156.800) -> Icecast (mount /ch16) -> Hetzner proxy
(`WICHITA_GROUND_VOICE_SOURCES=/opt/wichita/data/ground_voice_sources.json`). AIS stays on the SDRplay, untouched.

On the Mini (secrets live only there, mode 600):
- `~/wichita/live/icecast/secrets.env` (SRC_PW, ADMIN_PW, generated with `openssl rand -hex 24`)
- `~/wichita/live/icecast/icecast.xml`: listens on 100.114.183.100:8000 and 127.0.0.1:8000 only
- `~/wichita/live/airband/rtl_airband.conf`: see `rtl_airband.conf.template`
- rtl_airband built from source at `~/wichita/src/RTLSDR-Airband` (commit 32c7a00, `-DNFM=ON -DRTLSDR=ON`)
- Launch agents `com.sottosound.wichita.icecast` and `com.sottosound.wichita.airband`, KeepAlive,
  `LimitLoadToSessionType=Background`, loaded with `launchctl bootstrap user/501 <plist>` (no GUI session over ssh).

The macOS application firewall (stealth mode) must allow Icecast, or Hetzner gets no reply:
`sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /opt/homebrew/Cellar/icecast/2.4.4_4/bin/icecast --unblockapp /opt/homebrew/Cellar/icecast/2.4.4_4/bin/icecast`

Rollback (restores rtl_tcp on :1234):
```
launchctl bootout user/501/com.sottosound.wichita.airband
launchctl bootout user/501/com.sottosound.wichita.icecast
nohup /bin/sh ~/rtltcp-loop.sh >/dev/null 2>&1 &
# Hetzner: drop the WICHITA_GROUND_VOICE_SOURCES line from wichita-dashboard.service, daemon-reload, restart
```

Baseline log (added 2026-10-15): rtl_airband writes channel stats to `~/wichita/live/airband/stats.txt`
every 15 s (`stats_filepath` in the config). The launch agent `com.sottosound.wichita.airband-baseline`
runs `airband_baseline.py`, which appends noise floor, signal level, squelch threshold and the
squelch/activity counters to `~/wichita/live/airband/baseline.csv` once a minute. No audio is kept.
Use it to compare antennas: counters reset when rtl_airband restarts. Install the agent with
`launchctl bootstrap user/$(id -u) ~/Library/LaunchAgents/com.sottosound.wichita.airband-baseline.plist`
(`kickstart` on `gui/` fails over ssh; to restart rtl_airband over ssh, kill it and KeepAlive relaunches it).

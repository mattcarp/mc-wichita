# Kenneth 24/7 Services

This document tracks the production `systemd` services used on the Workshop NUC.

## Managed Units

### `kenneth-dashboard.service`
- Purpose: SvelteKit dashboard on port `4000`
- Unit path: `/etc/systemd/system/kenneth-dashboard.service`
- Key settings:
  - `Restart=always`
  - `RestartSec=10`
  - `StandardOutput=journal`
  - `StandardError=journal`
  - `WantedBy=multi-user.target`

### `kenneth-sentinel.service`
- Purpose: Sentinel API backend on port `4001`
- Unit path: `/etc/systemd/system/kenneth-sentinel.service`
- Exec:
  - `/usr/bin/python3 kenneth_sentinel_api.py`
- Key settings:
  - `Restart=always`
  - `RestartSec=10`
  - `StandardOutput=journal`
  - `StandardError=journal`
  - `WantedBy=multi-user.target`

### `kenneth-hunter.service`
- Purpose: Autonomous RF voice hunter
- Unit path: `/etc/systemd/system/kenneth-hunter.service`
- Exec:
  - `/usr/bin/python3 /home/sysop/projects/kenneth/autonomous_voice_hunter_real.py --hours 24`
- Key settings:
  - `Restart=always`
  - `RestartSec=10`
  - `StandardOutput=journal`
  - `StandardError=journal`
  - `WantedBy=multi-user.target`

## Disk Cleanup Automation

### Script
- Path: `/home/sysop/projects/kenneth/cleanup_captures.sh`
- Behavior:
  - Deletes `*.raw` and `*.wav` files older than `30` days under `/home/sysop/projects/kenneth`
  - Supports dry-run mode:
    - `/home/sysop/projects/kenneth/cleanup_captures.sh --dry-run`

### Timer + Service
- Unit files:
  - `/etc/systemd/system/kenneth-cleanup.service`
  - `/etc/systemd/system/kenneth-cleanup.timer`
- Schedule:
  - Daily at `03:00` (`OnCalendar=*-*-* 03:00:00`)
- Timer is persistent:
  - missed runs execute on next boot (`Persistent=true`)

## Journal Retention / Rotation

- Config path: `/etc/logrotate.d/kenneth`
- Runs with daily logrotate.
- Post-rotate actions:
  - `journalctl --rotate`
  - `journalctl --vacuum-time=30d`
  - `journalctl --vacuum-size=1G`

This bounds journal growth while keeping service logs in `journald`.

## Operational Commands

- Reload unit files:
  - `sudo systemctl daemon-reload`
- Restart services:
  - `sudo systemctl restart kenneth-dashboard.service kenneth-sentinel.service kenneth-hunter.service`
- Enable boot start:
  - `sudo systemctl enable kenneth-dashboard.service kenneth-sentinel.service kenneth-hunter.service kenneth-cleanup.timer`
- Inspect status:
  - `systemctl status kenneth-dashboard.service`
  - `systemctl status kenneth-sentinel.service`
  - `systemctl status kenneth-hunter.service`
  - `systemctl status kenneth-cleanup.timer`
- Check logs:
  - `journalctl -u kenneth-dashboard.service -f`
  - `journalctl -u kenneth-sentinel.service -f`
  - `journalctl -u kenneth-hunter.service -f`
  - `journalctl -u kenneth-cleanup.service -n 100`

# Wichita handover (written 2026-10-15)

Mattie is moving to another LLM. This is the current state. No secret values are in this file; secrets live in Infisical (Mattie's CLI on his MacBook Air, mattcarp1@gmail.com) and in Hetzner/Mini env and systemd files. Items marked (unverified) were not re-checked on 2026-10-15.

## What Wichita is
Voice and sentiment analysis of human voices on radio, to help vulnerable people (spoken distress, stress in the voice, not just the words). It is a one-user alpha, receive-only and non-commercial. Position data (ships via AIS, aircraft via ADS-B) is secondary context. Wichita has no Voice Lab; that belongs to another project. Never mention Kansas in copy. Never lean on "mayday". The receiver is a balcony in Valletta, Malta. Plural rule: only 1 is singular ("1 ship", "0 ships").

## Standing rules from Mattie
- Push straight to main, no PRs or branches. (AGENTS.md hard rules 4 and 6 say otherwise for Symphony runs; Mattie's rule for this project overrides.)
- Real data only. No mocks or fake numbers.
- Test everything visually on the live site before sending Mattie a link.
- The user's name must never show before sign-in or after sign-out.
- Every change must pass the Playwright visual suite in `tests/visual/`.
- Licensing: only add a data source if it serves Wichita's core purpose. Mattie accepts the risk for his one-user use and will comply with each licence if he ever commercialises.
- The dashboard feature freeze in AGENTS.md still applies (bug fixes, data correctness, security and listening features only).

## Current state
- Site: https://wichitawire.com, invite-only, "Solidarity print" design (files from MC God's Eye View, mockups in /workspace/mwv-mockups/v3 on the Grok box). H1 "Wichita", H2 "People in trouble rarely say the right words. Wichita listens for how they sound." Right-hand scrolling ship sidebar with an outside VesselFinder link, red balcony marker, "More details" triangles on expandable rows, Following panel filled with ship details, all tabs styled identically.
- Sky tab: aircraft from adsb.lol (`https://api.adsb.lol/v2/lat/35.9/lon/14.5/dist/250`, one server-side poller every 15 s, deduplicated by ICAO hex, source label per aircraft, 7500/7600/7700 pinned in red). A local antenna can feed in through `WICHITA_ADSB_URL`. OpenSky is skipped (needs a written licence).
- Ground voice (Heard tab): allowlist 145.500, 433.500, CB channel 9 (27.065), marine channel 16 (156.800), 121.5. Refused: TETRA, PMR446, DECT, phones. Listener caps: 3 per channel, 6 overall. Audio plays through our server with one-time tickets. Only scores are kept, plus clips scoring 70 or more for up to 72 h. Code: `wichita_ground_voice.py`, `wichita_ground_voice_routes.py`, test `test_wichita_ground_voice.py`. Env: `WICHITA_GROUND_VOICE_CLEARED=true` (legal gate, unlocked by Mattie on 2026-10-14 for his one-user non-commercial alpha, his responsibility; MCA/IDPC advice still recommended before wider use) and `WICHITA_GROUND_VOICE_SOURCES=/opt/wichita/data/ground_voice_sources.json`. A channel shows Live only when its receiver stream answers; otherwise "Receiver not answering".
- Ch16 chain is built on the Mini but Hetzner cannot reach Icecast until the firewall command below is run. It will be mostly silent until a proper antenna is fitted.

## Hardware
- Mac Mini `matts-mac-mini` (Tailscale 100.114.183.100, MagicDNS matts-mac-mini.tail6a2168.ts.net):
  - SDRplay RSPdx-R2 runs AIS-catcher, launch agent `com.sottosound.wichita.ais` (AIS on :8100 for Hetzner).
  - RTL-SDR Blog V4 runs rtl_airband (`com.sottosound.wichita.airband`) into Icecast (`com.sottosound.wichita.icecast`) at 100.114.183.100:8000, mount /ch16. Before this, the dongle ran rtl_tcp (`com.mattcarp.rtltcp`).
  - ADS-B feed endpoint configured as :8080/data/aircraft.json (unverified whether a local decoder is running).
  - No proper antenna yet.
- Planned antenna from Fabian (fabian.com.mt): Vehicle/Magnetic Scanner Antenna 25-1300 MHz, code JSKYSCAN, EUR 60.09, https://www.fabian.com.mt/en/products/webshop/17997/vehicle-magnetic-scanner-ant-25-1300mhz.htm, plus RF adapter SMA plug to BNC socket, code 04-LP2051, EUR 4.38, https://www.fabian.com.mt/en/products/webshop/19216/rf-adapter-sma-plug-bnc-socket.htm. No online ordering: phone +356 2131 3283, email sales@fabian.com.mt, or visit (Mon-Fri 8:30-17:30, Sat 8:30-12:00). Ask about courier delivery. Mattie plans to phone.
- ReSpeaker XVF3800 (owned). Raspberry Pi 5 (16 GB, owned, not in use): possible cheap second receiver site at a better antenna location, sending audio and scores over Tailscale like the Mini.
- Gram (kiosk display): relaunched after every deploy (commit 170166c).

## Hosting
- Hetzner 91.99.2.222, user `matt`. App at /opt/wichita/app (not a git checkout, files are uploaded), venv at /opt/wichita/venv, data at /opt/wichita/data, backups at /opt/wichita/backups. systemd unit `wichita-dashboard` (uvicorn on 127.0.0.1:3140, env set in the unit file; read it with `systemctl cat wichita-dashboard`). Tailscale links it to the Mini.
- DNS: wichitawire.com via Cloudflare, DNS-only A record to Hetzner. All hosting is on Hetzner.
- Auth: Clerk app `mc-wichita`, invite-only, passwordless email code or link, 15-day sessions. `WICHITA_AUTH_REQUIRED=true`. Production instance live since 2026-10-15: Frontend API `clerk.wichitawire.com` (DNS via Cloudflare Domain Connect, verified), set on Hetzner by the drop-in `ops/hetzner/clerk-prod.conf`. Code defaults remain the dev instance for local runs. Password sign-up is off in production (it came on with the clone). Production users are separate from dev: add people under Users > Create user.
- Secrets: Infisical (`infisical run --env=dev -- ...`), plus env on Hetzner and Mini files (Icecast passwords in `~/wichita/live/icecast/secrets.env` on the Mini, mode 600).

## Run, test, deploy
- Run locally: `infisical run --env=dev -- python3 api_server.py` (see AGENTS.md for ports). Python tests: `python3 -m pytest test_wichita_*.py test_plural_copy.py`.
- Visual suite: `tests/visual/` (Playwright against the live site, see its README). It reuses a saved Clerk storageState (`.auth/state.json`) so Mattie gets fewer verification-code emails; if it expires a code must be emailed and put in `.auth/code.txt`. Refresh baselines only for intended design changes.
- Deploy: there is no ssh/scp on the Grok box, so a paramiko helper (/workspace/hz.py on the Grok box, key ~/.ssh/hetzner_box, user matt) uploads whole files to /opt/wichita/app, backs up the old file first, then restarts `wichita-dashboard`. With normal ssh, do the same: copy the file, `sudo systemctl restart wichita-dashboard`. Bump the static cache key after front-end changes (previous keys: sp1 to sp10, gv1, 20261014-air2, then "air2" in dcf5c78). Then run the visual suite and look at the live site.
- Mini receiver runbook and rollback: `ops/ground-voice/README.md`.

## Open tasks
1. Done 2026-10-15 (ch16 reports Live from Hetzner). Firewall command for reference: `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /opt/homebrew/Cellar/icecast/2.4.4_4/bin/icecast --unblockapp /opt/homebrew/Cellar/icecast/2.4.4_4/bin/icecast`. Then check the Listen button on the live site.
2. Buy the antenna and adapter (above).
3. Fiona's background colour: she dislikes the bright yellow hero (`.fr-hero`, `--sun #f3c318`). Six numbered options were built as a page in the separate repo mattcarp/mc-sottosound-site, commit 168a263 ("mockups: Wichita background colour options"), NOT deployed and not Wichita's repo. Mattie has not answered about hosting it on Hetzner. Once she picks, change the hero colour only.
4. OpenSky licence email draft is unsent and OpenSky is skipped (Mattie is not attending the Madrid symposium). See `docs/notes/opensky.md`.
5. Google Maps API key (secret card `GOOGLE_MAPS_API_KEY`, not provided yet).
6. Decide which Irish city to feature.
7. Done 2026-10-15: Clerk production instance (see Hosting). The visual suite's saved `.auth/state.json` is a dev session and must be refreshed with one emailed code.
8. Hetzner disk: 99% on 2026-10-15, cleaned to 88% (8.7G free) the same day. /opt/wichita is small (backups 1.2M, data 60M); the space is containerd images (17G, in use), ~/.hermes (11G), ~/projects (9.5G) and ~/models (5.6G).
9. Legal opinions (MCA/IDPC) before wider ground-voice use. Pick a Maltese-capable ASR (candidate: mc-vuci Maltese Whisper, 19.37% WER on FLEURS mt). The freeze lifts only when one real received transmission shows end to end (see AGENTS.md).

## Known issues
- Ch16 shows "Receiver not answering" until the firewall step is done (accurate, not a bug).
- Hetzner disk nearly full (above).
- AGENTS.md hard rules conflict with the push-to-main rule (above).
- Stray tracked build files (`__pycache__`, `wichita-websdr/.next/trace`) show as deleted in old checkouts; harmless.
- Local checkouts on the Grok box (/workspace/taudit/mc-wichita, /workspace/wichita-research/mc-wichita) are stale; use a fresh clone of origin/main.

## Next steps
Run the firewall command, confirm ch16 Live in the browser, buy the antenna, hear a real transmission end to end (which lifts the freeze), then ADS-B from the local antenna, ASR choice, Clerk production keys, free up disk.

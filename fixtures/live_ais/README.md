# Live AIS API fixtures

Captured JSON/GeoJSON from AIS-catcher on the Mac Mini balcony receiver (`127.0.0.1:8100`). Used by `test_wichita_ais_live.py` and local dashboard verification.

Set `WICHITA_AIS_FIXTURE_DIR` to this directory to replay responses without hardware:

```bash
export WICHITA_AIS_FIXTURE_DIR="$(pwd)/fixtures/live_ais"
export WICHITA_CAPTURES_DIRS="$(pwd)/fixtures"
python3 api_server.py
```

No new dependencies: the API reads these files via `wichita_ais_live.fetch_ais_json`.

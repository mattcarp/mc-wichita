"""Persist alert records to JSONL so the review queue survives API restarts."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_lock = threading.Lock()


def alerts_dir() -> Path:
    raw = os.environ.get("WICHITA_ALERTS_DIR", "~/wichita/live/alerts").strip()
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def alerts_jsonl_path() -> Path:
    return alerts_dir() / "alerts.jsonl"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    return value


def append_alert_record(record: Dict[str, Any]) -> None:
    """Append one alert snapshot as a single JSONL line."""
    payload = _serialize_value(record)
    path = alerts_jsonl_path()
    line = json.dumps(payload, ensure_ascii=False)
    with _lock:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def load_alert_records(limit: int = 500) -> List[Dict[str, Any]]:
    """
    Load alerts from JSONL. When the same id appears more than once, the last line wins.
    """
    path = alerts_jsonl_path()
    if not path.is_file():
        return []

    by_id: Dict[str, Dict[str, Any]] = {}
    with _lock:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                alert_id = row.get("id")
                if not alert_id:
                    continue
                by_id[str(alert_id)] = row

    ordered = sorted(
        by_id.values(),
        key=lambda r: r.get("created_at") or "",
    )
    if len(ordered) > limit:
        ordered = ordered[-limit:]
    return ordered

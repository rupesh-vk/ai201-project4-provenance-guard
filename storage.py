import json
import os
from datetime import datetime, timezone

LOG_FILE = "audit_log.json"


def _read_log() -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _write_log(entries: list) -> None:
    with open(LOG_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def append_entry(entry: dict) -> None:
    """Append a single structured entry to the audit log."""
    entries = _read_log()
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    entries.append(entry)
    _write_log(entries)


def get_log(limit: int = 50) -> list:
    """Return the most recent log entries, newest first."""
    entries = _read_log()
    return list(reversed(entries))[:limit]


def find_entry_by_content_id(content_id: str) -> dict | None:
    """Find the most recent (original classification) entry for a content_id."""
    entries = _read_log()
    for entry in reversed(entries):
        if entry.get("content_id") == content_id and entry.get("status") == "classified":
            return entry
    return None
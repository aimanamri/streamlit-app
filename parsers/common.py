"""Shared helpers for the data parsers (HTTP, JSON writing, change detection)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HEADERS = {"User-Agent": "Mozilla/5.0 (streamlit-stock-app data updater; personal project)"}


def get(url: str, **kwargs) -> requests.Response:
    response = requests.get(url, headers={**HEADERS, **kwargs.pop("headers", {})}, timeout=kwargs.pop("timeout", 60), **kwargs)
    response.raise_for_status()
    return response


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_json_if_changed(path: Path, payload: dict) -> bool:
    """Write `payload` unless only `generated_at` differs. Returns True if the file changed."""
    old = read_json(path)
    strip = lambda d: {k: v for k, v in (d or {}).items() if k != "generated_at"}
    if old is not None and strip(old) == strip(payload):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return True

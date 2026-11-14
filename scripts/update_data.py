#!/usr/bin/env python
"""Refresh the data files the app ships with. Run locally or from GitHub Actions.

    python scripts/update_data.py            # everything
    python scripts/update_data.py shariah    # Shariah list only
    python scripts/update_data.py tickers    # dropdown ticker lists only

A source that fails keeps its previous data file untouched and makes the exit code 1 (so CI
shows it) without blocking the other sources.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers import shariah_my, tickers  # noqa: E402
from parsers.common import read_json, write_json_if_changed  # noqa: E402


def run_shariah() -> bool:
    payload = shariah_my.build()
    changed = write_json_if_changed(shariah_my.OUTPUT, payload)
    print(f"shariah_my: {payload['count']} securities, {payload['list_name']} -> {'updated' if changed else 'unchanged'}")
    return True


def run_tickers() -> bool:
    payload = tickers.build(read_json(shariah_my.OUTPUT))
    changed = write_json_if_changed(tickers.OUTPUT, payload)
    counts = {m: v["count"] for m, v in payload["markets"].items()}
    print(f"tickers: {counts} -> {'updated' if changed else 'unchanged'}")
    for market, err in payload["errors"].items():
        print(f"  WARNING {market}: {err} (kept previous list)")
    return not payload["errors"]


TASKS = {"shariah": run_shariah, "tickers": run_tickers}  # tickers after shariah: Bursa list uses it


def main(argv: list) -> int:
    names = argv or list(TASKS)
    failed = []
    for name in names:
        if name not in TASKS:
            print(f"Unknown task '{name}'. Choose from: {', '.join(TASKS)}")
            return 2
        try:
            if not TASKS[name]():
                failed.append(name)
        except Exception as err:
            print(f"{name}: FAILED - {err}")
            failed.append(name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

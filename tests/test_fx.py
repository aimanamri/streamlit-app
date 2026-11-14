"""Offline tests for the currency helpers."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fx import change_pct, market_note, money, rate_signal, summarise  # noqa: E402


def series(values, end="2026-11-13"):
    idx = pd.bdate_range(end=end, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def test_money_uses_zero_decimals_for_yen_and_rupiah():
    assert money(1234567.891, "IDR") == "1,234,568"
    assert money(1234.5, "MYR") == "1,234.50"


def test_change_pct_compares_with_earlier_fixing():
    s = series([100.0] * 40 + [110.0])
    assert round(change_pct(s, 7), 2) == 10.0
    assert change_pct(series([1.0]), 30) is None


def test_signal_flags_rate_above_and_below_average():
    up = summarise(series([4.0] * 60 + [4.4]))
    down = summarise(series([4.0] * 60 + [3.6]))
    assert rate_signal(up)[1] == "bull"
    assert rate_signal(down)[1] == "bear"
    assert rate_signal(summarise(series([4.0] * 61)))[1] == "hold"


def test_market_note_mentions_weekend():
    assert "weekends" in market_note(date(2026, 11, 13), date(2026, 11, 15))
    assert "reference fixing" in market_note(date(2026, 11, 13), date(2026, 11, 13))

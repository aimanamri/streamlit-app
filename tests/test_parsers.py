"""Offline tests: no network. Run with `pytest`."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import add_indicators, normalise_ticker, technical_signals, verdict  # noqa: E402
from parsers import shariah_my, tickers  # noqa: E402
from parsers.common import write_json_if_changed  # noqa: E402


def test_shariah_find_latest_picks_first_entry():
    html = ('..."pages":{"0":[{"name":" List as at 29 May 2026","file_path":"https://x/a.pdf","date_published":"May 29, 2026"},'
            '{"name":"List as at 28 Nov 2025","file_path":"https://x/b.pdf","date_published":"Nov 27, 2025"}]}')
    latest = shariah_my.find_latest(html)
    assert latest == {"name": "List as at 29 May 2026", "url": "https://x/a.pdf", "published": "May 29, 2026"}


def test_shariah_find_latest_fails_loudly_when_layout_changes():
    try:
        shariah_my.find_latest("<html>nothing here</html>")
    except shariah_my.ParseError:
        return
    raise AssertionError("expected ParseError")


def test_shariah_parse_text_handles_two_columns_and_ace_codes():
    text = "1. 7086 Ablegroup Bhd\n2. 5198 ABM Fujiya Bhd\n8. 03068 Bentley Music Group 27. 5327 Mega Fortris Bhd\nNo. Stock code Name"
    assert shariah_my.parse_text(text) == {
        "7086": "Ablegroup Bhd", "5198": "ABM Fujiya Bhd", "03068": "Bentley Music Group", "5327": "Mega Fortris Bhd"}


def test_clean_name_strips_share_class_suffixes():
    assert tickers.clean_name("Apple Inc. Common Stock") == "Apple Inc."


def test_write_json_if_changed_ignores_timestamp(tmp_path):
    path = tmp_path / "x.json"
    assert write_json_if_changed(path, {"generated_at": "a", "v": 1}) is True
    assert write_json_if_changed(path, {"generated_at": "b", "v": 1}) is False
    assert write_json_if_changed(path, {"generated_at": "c", "v": 2}) is True


def test_normalise_ticker_adds_market_suffix():
    assert normalise_ticker(" 1155 ", ".KL") == "1155.KL"
    assert normalise_ticker("7203.t", ".T") == "7203.T"
    assert normalise_ticker("aapl", "") == "AAPL"


def _prices(trend: float, n: int = 300, noise: float = 0.15) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    close = 100 + np.cumsum(rng.normal(trend, noise, n))
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1000}, index=idx)


def test_indicators_columns_and_ranges():
    d = add_indicators(_prices(0.2))
    assert {"SMA 200", "RSI", "MACD", "BB upper", "%K"} <= set(d.columns)
    assert d["RSI"].dropna().between(0, 100).all()


def test_uptrend_scores_bullish_and_downtrend_bearish():
    up = verdict(technical_signals(add_indicators(_prices(0.4))))[0]
    down = verdict(technical_signals(add_indicators(_prices(-0.4))))[0]
    assert "Buy" in up
    assert "Sell" in down

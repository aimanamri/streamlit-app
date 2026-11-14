"""Pure helpers for the currency converter (no Streamlit): rate statistics and a simple signal."""
from datetime import date

import pandas as pd

ZERO_DECIMAL = {"JPY", "IDR", "KRW"}


def decimals(currency: str) -> int:
    return 0 if currency in ZERO_DECIMAL else 2


def money(value: float, currency: str) -> str:
    return f"{value:,.{decimals(currency)}f}"


def change_pct(series: pd.Series, days: int) -> float | None:
    """% change of the latest rate versus `days` calendar days earlier (nearest earlier fixing)."""
    if series.empty:
        return None
    ref = series.index[-1] - pd.Timedelta(days=days)
    earlier = series.loc[:ref]
    if earlier.empty or earlier.iloc[-1] == 0:
        return None
    return (series.iloc[-1] / earlier.iloc[-1] - 1) * 100


def summarise(series: pd.Series) -> dict:
    last30 = series.loc[series.index >= series.index[-1] - pd.Timedelta(days=30)]
    last7 = series.loc[series.index >= series.index[-1] - pd.Timedelta(days=7)]
    year = series.loc[series.index >= series.index[-1] - pd.Timedelta(days=365)]
    span = year.max() - year.min()
    return {
        "today": series.iloc[-1], "date": series.index[-1],
        "chg_1d": change_pct(series, 1), "chg_7d": change_pct(series, 7), "chg_30d": change_pct(series, 30),
        "high30": last30.max(), "low30": last30.min(), "avg30": last30.mean(), "avg7": last7.mean(),
        "high52": year.max(), "low52": year.min(),
        "pos52": float((series.iloc[-1] - year.min()) / span) if span else 0.5,
    }


def rate_signal(stats: dict) -> tuple[str, str, str]:
    """(label, mood, reason) for converting base -> target: a higher rate means more target currency.

    mood is 'bull' (rate is good), 'hold' or 'bear' (rate is poor), compared with the 30-day average.
    """
    gap = (stats["today"] / stats["avg30"] - 1) * 100
    near_top = stats["pos52"] >= 0.8
    near_bottom = stats["pos52"] <= 0.2
    if gap >= 1.0:
        label, mood = "Favourable rate", "bull"
    elif gap <= -1.0:
        label, mood = "Weak rate", "bear"
    else:
        label, mood = "Average rate", "hold"
    reason = f"{abs(gap):.1f}% {'above' if gap >= 0 else 'below'} the 30-day average"
    if near_top:
        reason += "; near the 1-year high"
    elif near_bottom:
        reason += "; near the 1-year low"
    return label, mood, reason


def market_note(latest: date, today: date) -> str:
    """Explain static rates: forex is closed at weekends and ECB fixings come out on working days."""
    if today.weekday() >= 5:
        return f"Forex markets are closed at weekends, so rates stay at the {latest:%d %b %Y} fixing."
    if latest < today:
        return f"Today's fixing is not out yet (the ECB publishes around 16:00 CET); showing {latest:%d %b %Y}."
    return "Rates are the ECB reference fixing for today."

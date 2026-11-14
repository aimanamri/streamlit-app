"""Pure functions (no Streamlit): ticker handling, indicators and rule-based signals."""
import pandas as pd


def normalise_ticker(raw: str, suffix: str) -> str:
    t = raw.strip().upper().replace(" ", "")
    if suffix and not t.endswith(suffix):
        t = t.split(".")[0] + suffix
    return t


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d, c = df.copy(), df["Close"]
    for n in (20, 50, 200):
        d[f"SMA {n}"] = c.rolling(n).mean()
    for n in (12, 26):
        d[f"EMA {n}"] = c.ewm(span=n, adjust=False).mean()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    d["BB mid"], d["BB upper"], d["BB lower"] = mid, mid + 2 * sd, mid - 2 * sd
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))
    d["MACD"] = d["EMA 12"] - d["EMA 26"]
    d["MACD signal"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACD hist"] = d["MACD"] - d["MACD signal"]
    low14, high14 = df["Low"].rolling(14).min(), df["High"].rolling(14).max()
    d["%K"] = 100 * (c - low14) / (high14 - low14).replace(0, float("nan"))
    d["%D"] = d["%K"].rolling(3).mean()
    return d


def technical_signals(d: pd.DataFrame) -> list[dict]:
    """One row per indicator: +1 bullish, 0 neutral, -1 bearish, with the reason."""
    last, prev = d.iloc[-1], d.iloc[-2] if len(d) > 1 else d.iloc[-1]
    rows = []

    def add(name, value, score, reason):
        # Trend indicators count double: oscillators (RSI, Stochastic, Bollinger) vote against the
        # trend near extremes and would otherwise cancel it out.
        weight = 2 if name.startswith(("Price vs", "SMA", "MACD")) else 1
        rows.append({"Indicator": name, "Value": value, "Score": score, "Weight": weight, "Reading": reason})

    price = last["Close"]
    for n in (50, 200):
        sma = last.get(f"SMA {n}")
        if pd.notna(sma):
            up = price > sma
            add(f"Price vs SMA {n}", f"{price:,.2f} vs {sma:,.2f}", 1 if up else -1,
                f"Trading {'above' if up else 'below'} the {n}-day average")
    if pd.notna(last["SMA 200"]):
        up = last["SMA 50"] > last["SMA 200"]
        add("SMA 50 vs 200", f"{last['SMA 50']:,.2f} vs {last['SMA 200']:,.2f}", 1 if up else -1,
            "Golden-cross regime (50 above 200)" if up else "Death-cross regime (50 below 200)")
    if pd.notna(last["MACD signal"]):
        above_signal, above_zero = last["MACD"] > last["MACD signal"], last["MACD"] > 0
        rising = last["MACD hist"] > prev["MACD hist"]
        score = 1 if (above_signal and above_zero) else -1 if (not above_signal and not above_zero) else 0
        mood = {1: "bullish: above its signal line and above zero", -1: "bearish: below its signal line and below zero",
                0: "mixed: signal line and zero line disagree"}[score]
        add("MACD", f"{last['MACD']:.2f} / {last['MACD signal']:.2f}", score,
            f"MACD {mood}; histogram {'rising' if rising else 'falling'}")
    rsi = last["RSI"]
    if pd.notna(rsi):
        if rsi < 30:
            add("RSI (14)", f"{rsi:.1f}", 1, "Oversold (below 30): possible rebound")
        elif rsi > 70:
            add("RSI (14)", f"{rsi:.1f}", -1, "Overbought (above 70): possible pullback")
        else:
            add("RSI (14)", f"{rsi:.1f}", 0, "In the neutral 30-70 range")
    k = last["%K"]
    if pd.notna(k):
        if k < 20:
            add("Stochastic %K", f"{k:.1f}", 1, "Oversold (below 20)")
        elif k > 80:
            add("Stochastic %K", f"{k:.1f}", -1, "Overbought (above 80)")
        else:
            add("Stochastic %K", f"{k:.1f}", 0, "In the neutral 20-80 range")
    if pd.notna(last["BB lower"]):
        if price < last["BB lower"]:
            add("Bollinger Bands", f"{price:,.2f}", 1, "Closed below the lower band: stretched down")
        elif price > last["BB upper"]:
            add("Bollinger Bands", f"{price:,.2f}", -1, "Closed above the upper band: stretched up")
        else:
            add("Bollinger Bands", f"{price:,.2f}", 0, "Inside the bands")
    return rows


def verdict(rows: list[dict]) -> tuple[str, str]:
    """(label, art key) from the average indicator score."""
    if not rows:
        return "Not enough history", "hold"
    avg = sum(r["Score"] * r["Weight"] for r in rows) / sum(r["Weight"] for r in rows)
    if avg >= 0.6:
        return "Strong Buy", "bull"
    if avg >= 0.2:
        return "Buy", "bull"
    if avg > -0.2:
        return "Neutral / Hold", "hold"
    if avg > -0.6:
        return "Sell", "bear"
    return "Strong Sell", "bear"


def pct(a, b):
    return (a / b - 1) * 100 if b else float("nan")

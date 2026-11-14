"""Stock Analysis App: NASDAQ, Bursa Malaysia and Japan (Tokyo).

Candlestick charts with common technical indicators, a rule-based technical signal
summary, comparison with earlier weeks / months / years, and the Securities
Commission Malaysia Shariah status for Bursa Malaysia stocks.

Educational tool only. Signals come from simple indicator rules and are not
investment advice.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots
from analysis import add_indicators, normalise_ticker, pct, technical_signals, verdict
from parsers import shariah_my

st.set_page_config(page_title="Stock Analysis App", page_icon="📈", layout="wide")

# ----------------------------------------------------------------- markets ----
MARKETS = {
    "NASDAQ": {"suffix": "", "flag": "🇺🇸", "tickers": {
        "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "GOOGL": "Alphabet (Google)",
        "AMZN": "Amazon", "META": "Meta Platforms", "TSLA": "Tesla", "AVGO": "Broadcom",
        "COST": "Costco", "NFLX": "Netflix", "AMD": "AMD", "ADBE": "Adobe", "PEP": "PepsiCo",
        "CSCO": "Cisco", "INTC": "Intel", "QCOM": "Qualcomm", "TXN": "Texas Instruments",
        "AMGN": "Amgen", "INTU": "Intuit", "BKNG": "Booking Holdings", "SBUX": "Starbucks",
        "ZM": "Zoom", "MU": "Micron", "PYPL": "PayPal", "ASML": "ASML"}},
    "Bursa Malaysia": {"suffix": ".KL", "flag": "🇲🇾", "tickers": {
        "1155": "Maybank", "1023": "CIMB Group", "1295": "Public Bank", "1066": "RHB Bank",
        "5819": "Hong Leong Bank", "5347": "Tenaga Nasional", "5183": "Petronas Chemicals",
        "6033": "Petronas Gas", "5681": "Petronas Dagangan", "3816": "MISC", "5225": "IHH Healthcare",
        "6888": "Axiata", "6947": "CelcomDigi", "4863": "Telekom Malaysia", "4707": "Nestle Malaysia",
        "5285": "SD Guthrie", "2445": "Kuala Lumpur Kepong", "1961": "IOI Corporation",
        "8869": "Press Metal", "0166": "Inari Amertron", "5296": "MR DIY", "5099": "Capital A",
        "5398": "Gamuda", "5211": "Sunway", "3182": "Genting", "4715": "Genting Malaysia",
        "7113": "Top Glove", "5168": "Hartalega", "4065": "PPB Group"}},
    "Japan (Tokyo)": {"suffix": ".T", "flag": "🇯🇵", "tickers": {
        "7203": "Toyota", "6758": "Sony", "9984": "SoftBank Group", "8306": "Mitsubishi UFJ",
        "6861": "Keyence", "9432": "NTT", "6098": "Recruit", "8035": "Tokyo Electron",
        "7974": "Nintendo", "9983": "Fast Retailing", "6501": "Hitachi", "7267": "Honda",
        "8058": "Mitsubishi Corp", "4063": "Shin-Etsu Chemical", "6367": "Daikin", "9433": "KDDI",
        "4502": "Takeda", "8316": "Sumitomo Mitsui", "6902": "Denso", "7741": "HOYA"}},
}
RANGES = {"1M": 30, "3M": 91, "6M": 182, "1Y": 365, "3Y": 3 * 365, "5Y": 5 * 365}
SC_PAGE = "https://www.sc.com.my/development/icm/shariah-compliant-securities/list-of-shariah-compliant-securities"
HEADERS = {"User-Agent": "Mozilla/5.0 (streamlit-stock-app; personal project)"}
JST_MYT = timezone(timedelta(hours=8))


def stamp() -> str:
    return datetime.now(JST_MYT).strftime("%Y-%m-%d %H:%M (UTC+8)")


# ------------------------------------------------------------------- data ----
@st.cache_data(ttl=900, show_spinner="Loading prices from Yahoo Finance...")
def load_prices(symbol: str, start: date) -> dict:
    """Daily prices from 3 years + before `start`, so indicators and comparisons have history."""
    fetch_start = start - timedelta(days=3 * 365 + 40)
    df = yf.Ticker(symbol).history(start=fetch_start, end=date.today() + timedelta(days=1))
    if not df.empty:
        df.index = df.index.tz_localize(None).normalize()
        df = df[~df.index.duplicated(keep="last")]
    return {"df": df, "fetched_at": stamp()}


@st.cache_data(ttl=24 * 3600)
def load_info(symbol: str) -> dict:
    try:
        info = yf.Ticker(symbol).info
        return {"name": info.get("longName") or info.get("shortName") or symbol,
                "currency": info.get("currency", ""), "exchange": info.get("fullExchangeName", "")}
    except Exception:
        return {"name": symbol, "currency": "", "exchange": ""}


DATA_DIR = Path(__file__).parent / "data"


def read_data(name: str):
    try:
        return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@st.cache_data(ttl=3600)
def load_shariah_list() -> dict | None:
    """SC Malaysia Shariah list. Uses data/shariah_my.json (refreshed by the scheduled GitHub
    Action); only if that file is missing does it fetch the SC PDF itself."""
    data = read_data("shariah_my.json")
    if data:
        return {"codes": set(data["securities"]), "names": data["securities"], "name": data["list_name"],
                "published": data["published"], "fetched_at": data["generated_at"]}
    try:
        live = shariah_my.build()
        return {"codes": set(live["securities"]), "names": live["securities"], "name": live["list_name"],
                "published": live["published"], "fetched_at": live["generated_at"]}
    except Exception:
        return None


@st.cache_data(ttl=3600)
def market_tickers(market: str) -> tuple[dict, str]:
    """({code: name}, updated-at) for the dropdown: the data file, else the short built-in list."""
    data = read_data("tickers.json")
    if data and market in data.get("markets", {}):
        return data["markets"][market]["tickers"], data["generated_at"]
    return MARKETS[market]["tickers"], ""


# ------------------------------------------------------------------- charts ----
def main_chart(d: pd.DataFrame, chart_type: str, overlays: list, panels: list) -> go.Figure:
    rows = 1 + len(panels)
    heights = [0.55] + [0.45 / max(len(panels), 1)] * len(panels) if panels else [1]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=heights)
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
                                     name="Price", increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), 1, 1)
    else:
        fig.add_trace(go.Scatter(x=d.index, y=d["Close"], name="Close", line=dict(width=2)), 1, 1)
    palette = {"SMA 20": "#f5a623", "SMA 50": "#4a90e2", "SMA 200": "#b57edc", "EMA 12": "#50e3c2", "EMA 26": "#e9546b"}
    for name in overlays:
        if name == "Bollinger Bands":
            for col, dash in (("BB upper", "dot"), ("BB lower", "dot")):
                fig.add_trace(go.Scatter(x=d.index, y=d[col], name=col, line=dict(width=1, dash=dash, color="#9e9e9e")), 1, 1)
        else:
            fig.add_trace(go.Scatter(x=d.index, y=d[name], name=name, line=dict(width=1.4, color=palette[name])), 1, 1)
    for i, panel in enumerate(panels, start=2):
        if panel == "Volume":
            colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(d["Close"], d["Open"])]
            fig.add_trace(go.Bar(x=d.index, y=d["Volume"], name="Volume", marker_color=colors), i, 1)
        elif panel == "RSI":
            fig.add_trace(go.Scatter(x=d.index, y=d["RSI"], name="RSI 14", line=dict(color="#f5a623")), i, 1)
            fig.add_hline(y=70, line_dash="dot", line_color="#ef5350", row=i, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="#26a69a", row=i, col=1)
            fig.update_yaxes(range=[0, 100], row=i, col=1)
        elif panel == "MACD":
            colors = ["#26a69a" if v >= 0 else "#ef5350" for v in d["MACD hist"].fillna(0)]
            fig.add_trace(go.Bar(x=d.index, y=d["MACD hist"], name="MACD hist", marker_color=colors), i, 1)
            fig.add_trace(go.Scatter(x=d.index, y=d["MACD"], name="MACD", line=dict(color="#4a90e2")), i, 1)
            fig.add_trace(go.Scatter(x=d.index, y=d["MACD signal"], name="Signal", line=dict(color="#f5a623")), i, 1)
        elif panel == "Stochastic":
            fig.add_trace(go.Scatter(x=d.index, y=d["%K"], name="%K", line=dict(color="#4a90e2")), i, 1)
            fig.add_trace(go.Scatter(x=d.index, y=d["%D"], name="%D", line=dict(color="#f5a623")), i, 1)
            fig.add_hline(y=80, line_dash="dot", line_color="#ef5350", row=i, col=1)
            fig.add_hline(y=20, line_dash="dot", line_color="#26a69a", row=i, col=1)
            fig.update_yaxes(range=[0, 100], row=i, col=1)
        fig.update_yaxes(title_text=panel, row=i, col=1)
    fig.update_layout(height=420 + 170 * len(panels), margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.04), hovermode="x unified")
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


def overlay_chart(full: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, mode: str) -> go.Figure | None:
    """Current window vs an earlier window, both rebased to 100 and aligned by trading day."""
    if mode == "Previous period":
        shift = end - start
        p_start, p_end = start - shift, start
        label = "Previous period"
    else:
        years = 1 if mode == "Same period last year" else 2
        p_start, p_end = start - pd.DateOffset(years=years), end - pd.DateOffset(years=years)
        label = f"{years} year{'s' if years > 1 else ''} earlier"
    now = full.loc[start:end, "Close"]
    then = full.loc[p_start:p_end, "Close"]
    if len(now) < 2 or len(then) < 2:
        return None
    fig = go.Figure()
    for series, name, color in ((now, "Selected period", "#4a90e2"), (then, label, "#f5a623")):
        fig.add_trace(go.Scatter(x=list(range(1, len(series) + 1)), y=series / series.iloc[0] * 100, name=name,
                                 line=dict(color=color, width=2), customdata=series.index.strftime("%d %b %Y"),
                                 hovertemplate="%{customdata}: %{y:.1f}<extra>" + name + "</extra>"))
    fig.add_hline(y=100, line_dash="dot", line_color="#9e9e9e")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Trading day of the window",
                      yaxis_title="Indexed (start = 100)", legend=dict(orientation="h", y=1.08))
    return fig


# --------------------------------------------------------------------- UI ----
def art(name: str, width: int = 72):
    st.image(f"images/art-{name}.gif", width=width)  # pixel art made with Pixelbolt


top_art, top_title = st.columns([2, 5], vertical_alignment="center")
with top_art:
    st.image("images/banner.gif", width=300)
top_title.title("Stock Analysis App")
top_title.caption("NASDAQ · Bursa Malaysia · Japan (Tokyo) — charts, indicators, signals and period comparison")

st.sidebar.header("Choose a stock")
market = st.sidebar.selectbox("Market", list(MARKETS), format_func=lambda m: f"{MARKETS[m]['flag']} {m}")
cfg = MARKETS[market]
listed, listed_at = market_tickers(market)
shariah = load_shariah_list() if market == "Bursa Malaysia" else None
if shariah and st.sidebar.checkbox("Only Shariah-compliant stocks", help="Limits the list to the SC Malaysia Shariah-compliant securities."):
    listed = {c: n for c, n in listed.items() if c in shariah["codes"]}
pick = st.sidebar.selectbox(
    f"Pick from the list ({len(listed):,} stocks, type to search)", sorted(listed),
    index=sorted(listed).index(next(iter(cfg["tickers"]))) if next(iter(cfg["tickers"])) in listed else 0,
    format_func=lambda t: f"{t} – {listed[t]}",
)
typed = st.sidebar.text_input(
    "…or type a ticker",
    placeholder={"NASDAQ": "e.g. AAPL", "Bursa Malaysia": "e.g. 1155 or 03068", "Japan (Tokyo)": "e.g. 7203"}[market],
    help="Typing a ticker overrides the list. The market suffix (.KL / .T) is added for you.",
)
symbol = normalise_ticker(typed or pick, cfg["suffix"])

st.sidebar.header("Period")
choice = st.sidebar.radio("Range", list(RANGES) + ["Custom"], index=list(RANGES).index("1Y"), horizontal=True)
today = date.today()
if choice == "Custom":
    start_date = st.sidebar.date_input("Start date", value=today - timedelta(days=365), max_value=today)
    end_date = st.sidebar.date_input("End date", value=today, max_value=today)
else:
    start_date, end_date = today - timedelta(days=RANGES[choice]), today
if start_date >= end_date:
    st.error("Start date must be before end date.")
    st.stop()

st.sidebar.header("Chart")
chart_type = st.sidebar.radio("Type", ["Candlestick", "Line"], horizontal=True)
overlays = st.sidebar.multiselect(
    "Overlays", ["SMA 20", "SMA 50", "SMA 200", "EMA 12", "EMA 26", "Bollinger Bands"], default=["SMA 50", "SMA 200"])
panels = st.sidebar.multiselect("Panels", ["Volume", "RSI", "MACD", "Stochastic"], default=["Volume", "RSI", "MACD"])
compare_mode = st.sidebar.selectbox("Compare with", ["Same period last year", "Previous period", "Same period 2 years ago"])

if st.sidebar.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

# ---- load ----
try:
    loaded = load_prices(symbol, start_date)
except Exception as err:
    st.error(f"Could not load data for {symbol} from Yahoo Finance. ({err})")
    st.stop()
full = loaded["df"]
if full.empty or len(full) < 30:
    st.warning(
        f"No usable price data for **{symbol}**. Check the ticker "
        f"({'e.g. 1155 for Maybank' if market == 'Bursa Malaysia' else 'e.g. 7203 for Toyota' if market.startswith('Japan') else 'e.g. AAPL'})."
    )
    st.stop()

ind = add_indicators(full)
view = ind.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)]
if len(view) < 2:
    st.warning("Not enough trading days in the selected period. Choose a longer range.")
    st.stop()

info = load_info(symbol)
ccy = info["currency"]
last, first = view.iloc[-1], view.iloc[0]
day_change = pct(last["Close"], view["Close"].iloc[-2])

# ---- header + shariah ----
head, badge = st.columns([3, 2], vertical_alignment="top")
with head:
    st.subheader(f"{info['name']} ({symbol})")
    st.caption(f"{info['exchange']} · prices in {ccy or 'local currency'} · last trading day {view.index[-1]:%d %b %Y}")
with badge:
    if market == "Bursa Malaysia":
        code = symbol.replace(".KL", "")
        if shariah is None:
            st.warning("Shariah status unavailable right now (could not read the SC Malaysia list).")
        else:
            ok = code in shariah["codes"]
            a, b = st.columns([1, 4], vertical_alignment="center")
            if ok:
                with a:
                    art("shield", 56)
                b.success(f"**Shariah-compliant**\n\n{shariah['name']}")
            else:
                b.error(
                    "**Not on the SC Shariah-compliant list**\n\n"
                    f"{shariah['name']}. It may be non-compliant, newly listed or an ETF/REIT; verify at sc.com.my."
                )
    else:
        st.caption("Shariah status is shown for Bursa Malaysia stocks only.")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Last close", f"{last['Close']:,.2f}", f"{day_change:+.2f}% today")
m2.metric("Period return", f"{pct(last['Close'], first['Close']):+.2f}%", f"since {view.index[0]:%d %b %Y}")
hi52 = ind["Close"].iloc[-252:].max()
lo52 = ind["Close"].iloc[-252:].min()
m3.metric("52-week range", f"{lo52:,.2f} – {hi52:,.2f}", f"{pct(last['Close'], hi52):+.1f}% from high", delta_color="off")
vol = view["Close"].pct_change().std() * (252 ** 0.5) * 100
m4.metric("Volatility (annualised)", f"{vol:.1f}%")
dd = ((view["Close"] / view["Close"].cummax()) - 1).min() * 100
m5.metric("Max drawdown", f"{dd:.1f}%")

tab_chart, tab_signals, tab_compare, tab_data = st.tabs(["📈 Chart", "🧭 Signals", "🔁 Compare", "🗂 Data"])

with tab_chart:
    st.plotly_chart(main_chart(view, chart_type, overlays, panels), width="stretch")
    st.caption("Drag to zoom, double-click to reset, hover for exact values. Weekends are hidden.")

with tab_signals:
    rows = technical_signals(ind)
    label, mood = verdict(rows)
    buys = sum(r["Score"] > 0 for r in rows)
    sells = sum(r["Score"] < 0 for r in rows)
    holds = len(rows) - buys - sells
    colour = {"bull": "#26a69a", "bear": "#ef5350", "hold": "#f5a623"}[mood]
    g1, g2 = st.columns([1, 5], vertical_alignment="center")
    with g1:
        art(mood, 110)
    with g2:
        st.markdown(f"### Technical signal: <span style='color:{colour}'>{label}</span>", unsafe_allow_html=True)
        st.write(f"{buys} bullish · {holds} neutral · {sells} bearish, from {len(rows)} indicators as of "
                 f"{ind.index[-1]:%d %b %Y}.")
    table = pd.DataFrame(rows)
    table["Signal"] = table["Score"].map({1: "🟢 Buy", 0: "🟡 Neutral", -1: "🔴 Sell"})
    st.dataframe(table[["Indicator", "Value", "Signal", "Reading"]], hide_index=True, width="stretch")

    st.markdown("#### Key levels")
    prev = ind.iloc[-2]
    pivot = (prev["High"] + prev["Low"] + prev["Close"]) / 3
    levels = pd.DataFrame([
        ("Resistance 2 (pivot)", pivot + (prev["High"] - prev["Low"])),
        ("Resistance 1 (pivot)", 2 * pivot - prev["Low"]),
        ("20-day high", ind["High"].iloc[-20:].max()),
        ("Bollinger upper", last["BB upper"]),
        ("Last close", last["Close"]),
        ("Bollinger lower", last["BB lower"]),
        ("20-day low", ind["Low"].iloc[-20:].min()),
        ("Support 1 (pivot)", 2 * pivot - prev["High"]),
        ("Support 2 (pivot)", pivot - (prev["High"] - prev["Low"])),
        ("52-week low", lo52),
    ], columns=["Level", "Price"]).dropna().sort_values("Price", ascending=False)
    levels["vs last close"] = levels["Price"].map(lambda p: f"{pct(p, last['Close']):+.1f}%")
    levels["Price"] = levels["Price"].map(lambda p: f"{p:,.2f}")
    st.dataframe(levels, hide_index=True, width="stretch")
    st.info(
        "**Educational only, not investment advice.** The signal is a simple vote of standard indicator rules "
        "(trend, momentum, overbought/oversold) and ignores fundamentals, news, fees and your own situation. "
        "Indicators lag and often disagree; do your own research or ask a licensed adviser before trading."
    )

with tab_compare:
    st.markdown("#### Price now vs earlier")
    closes = full["Close"]
    now_price, now_date = closes.iloc[-1], closes.index[-1]
    lookbacks = [("1 week", pd.DateOffset(weeks=1)), ("1 month", pd.DateOffset(months=1)),
                 ("3 months", pd.DateOffset(months=3)), ("6 months", pd.DateOffset(months=6)),
                 ("1 year", pd.DateOffset(years=1)), ("2 years", pd.DateOffset(years=2)), ("3 years", pd.DateOffset(years=3))]
    comp = []
    for name, off in lookbacks:
        ref = now_date - off
        if ref < closes.index[0]:
            continue
        then = closes.loc[:ref].iloc[-1]
        comp.append({"Compared with": f"{name} ago", "Date": f"{closes.loc[:ref].index[-1]:%d %b %Y}",
                     "Price then": f"{then:,.2f}", "Change": f"{pct(now_price, then):+.2f}%"})
    st.dataframe(pd.DataFrame(comp), hide_index=True, width="stretch")

    st.markdown(f"#### Selected period vs {compare_mode.lower()}")
    fig = overlay_chart(full, pd.Timestamp(start_date), pd.Timestamp(end_date), compare_mode)
    if fig is None:
        st.info("Not enough earlier history for that comparison. Try a shorter range or another comparison.")
    else:
        st.plotly_chart(fig, width="stretch")

    st.markdown("#### Monthly and yearly returns")
    monthly = closes.resample("ME").last().pct_change().dropna() * 100
    yearly = closes.resample("YE").last().pct_change().dropna() * 100
    c1, c2 = st.columns(2)
    mfig = go.Figure(go.Bar(x=monthly.index[-12:].strftime("%b %Y"), y=monthly.iloc[-12:],
                            marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in monthly.iloc[-12:]]))
    mfig.update_layout(height=300, title="Last 12 months (%)", margin=dict(l=10, r=10, t=40, b=10))
    c1.plotly_chart(mfig, width="stretch")
    yfig = go.Figure(go.Bar(x=yearly.index.year.astype(str), y=yearly,
                            marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in yearly]))
    yfig.update_layout(height=300, title="Calendar years (%, latest year is partial)", margin=dict(l=10, r=10, t=40, b=10))
    c2.plotly_chart(yfig, width="stretch")

with tab_data:
    shown = view[["Open", "High", "Low", "Close", "Volume", "SMA 20", "SMA 50", "SMA 200", "RSI", "MACD", "MACD signal"]].round(3)
    st.dataframe(shown.sort_index(ascending=False), width="stretch")
    st.download_button("Download as CSV", shown.to_csv().encode("utf-8"), f"{symbol}.csv", "text/csv")

# ---- footer ----
foot = f"Prices fetched {loaded['fetched_at']} from Yahoo Finance (cached 15 min; may be delayed)."
if shariah:
    foot += f" Shariah list: {shariah['name']}, published {shariah['published']}, data file generated {shariah['fetched_at']}."
st.caption(foot)
with st.expander("About"):
    st.markdown(
        """
- **Markets:** NASDAQ, Bursa Malaysia (`.KL`) and Tokyo Stock Exchange (`.T`). Type any ticker or code, or use the list.
- **Indicators:** SMA 20/50/200, EMA 12/26, Bollinger Bands (20, 2), RSI 14, MACD (12, 26, 9), Stochastic (14, 3).
- **Shariah status:** from the [SC Malaysia list](https://www.sc.com.my/development/icm/shariah-compliant-securities/list-of-shariah-compliant-securities), updated by the SC every May and November.
- **Data:** [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance). Pixel art made with [Pixelbolt](https://github.com/skulitom/Pixelbolt).
"""
    )

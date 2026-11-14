from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from fx import market_note, money, rate_signal, summarise

st.set_page_config(page_title="Currency Converter", page_icon="💱", layout="wide")

API = "https://api.frankfurter.dev/v1"
CURRENCIES = ["JPY", "IDR", "MYR", "USD", "SGD", "KRW", "CNY", "EUR", "GBP", "AUD", "THB", "INR"]
PRESETS = [10, 50, 100, 1000, 10000]
FEES = {
    "0% Mid-market (interbank)": 0.0, "1% Online transfer": 1.0, "2% Card / bank": 2.0,
    "3% Money changer": 3.0, "5% Airport kiosk": 5.0, "Custom": None,
}


def stamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M (UTC+8)")


@st.cache_data(ttl=3600, show_spinner="Loading exchange rates...")
def load_history(base: str) -> dict:
    """One year of daily rates from `base` to every supported currency (one request)."""
    start = date.today() - timedelta(days=370)
    symbols = ",".join(c for c in CURRENCIES if c != base)
    response = requests.get(f"{API}/{start}..", params={"base": base, "symbols": symbols}, timeout=20)
    response.raise_for_status()
    frame = pd.DataFrame(response.json()["rates"]).T
    frame.index = pd.to_datetime(frame.index)
    return {"rates": frame.sort_index(), "fetched_at": stamp()}


# ------------------------------------------------------------- state / UI ----
def init_state():
    st.session_state.setdefault("amount", 100.0)
    st.session_state.setdefault("base", "USD")
    st.session_state.setdefault("target", "MYR")


def swap():
    st.session_state.base, st.session_state.target = st.session_state.target, st.session_state.base


def set_amount(value: float):
    st.session_state.amount = float(value)


init_state()
logo, head = st.columns([1, 6], vertical_alignment="center")
logo.image("images/art-currency.gif", width=96)  # pixel art made with Pixelbolt
head.title("Currency Converter App")
head.caption("Live ECB reference rates with fees, 1-year trend and a simple rate signal")

st.sidebar.header("Convert")
st.sidebar.number_input("Amount", min_value=0.0, step=10.0, key="amount")
for row in (PRESETS[:3], PRESETS[3:]):
    for col, preset in zip(st.sidebar.columns(3), row):
        col.button(f"{preset:,}", key=f"p{preset}", on_click=set_amount, args=(preset,), width="stretch")
st.sidebar.selectbox("From (base)", CURRENCIES, key="base")
st.sidebar.button("⇅ Swap currencies", on_click=swap, width="stretch")
st.sidebar.selectbox("To (target)", CURRENCIES, key="target")

fee_label = st.sidebar.selectbox("What you'd really pay", list(FEES))
fee = FEES[fee_label] if FEES[fee_label] is not None else st.sidebar.slider("Fee / spread (%)", 0.0, 10.0, 2.0, 0.1)
if st.sidebar.button("Refresh rates"):
    st.cache_data.clear()
    st.rerun()

amount, base, target = st.session_state.amount, st.session_state.base, st.session_state.target
if base == target:
    st.info("Base and target currency are the same. Pick two different currencies.")
    st.stop()

try:
    loaded = load_history(base)
except (requests.RequestException, KeyError, ValueError) as err:
    st.error(f"Could not load exchange rates. Please try again later. ({err})")
    st.stop()
history = loaded["rates"]
series = history[target].dropna()
stats = summarise(series)
rate = stats["today"]
received = amount * rate * (1 - fee / 100)

# ----------------------------------------------------------------- result ----
st.subheader("Result")
r1, r2, r3 = st.columns(3)
r1.metric("You convert", f"{base} {money(amount, base)}")
r2.metric("You receive" if fee else "Mid-market value", f"{target} {money(received, target)}",
          f"-{fee:g}% fee" if fee else None, delta_color="inverse")
r3.metric("Rate", f"1 {base} = {rate:,.4f} {target}", f"1 {target} = {1 / rate:,.4f} {base}", delta_color="off")
st.code(f"{base} {money(amount, base)} = {target} {money(received, target)}", language=None)  # has a copy button
if fee:
    lost = amount * rate - received
    st.caption(f"The {fee:g}% fee costs about {target} {money(lost, target)} compared with the mid-market rate.")

# ---------------------------------------------------------------- signals ----
st.subheader(f"{base} → {target} trend")
label, mood, reason = rate_signal(stats)
s1, s2 = st.columns([1, 6], vertical_alignment="center")
s1.image(f"images/art-{mood}.gif", width=80)  # pixel art made with Pixelbolt
colour = {"bull": "#26a69a", "bear": "#ef5350", "hold": "#f5a623"}[mood]
s2.markdown(f"### <span style='color:{colour}'>{label}</span>", unsafe_allow_html=True)
s2.write(f"Today's rate is {reason}. A higher {base}→{target} rate means you get more {target} per {base}.")

c = st.columns(6)
fmt = lambda v: "n/a" if v is None else f"{v:+.2f}%"
c[0].metric("1 day", fmt(stats["chg_1d"]), fmt(stats["chg_1d"]), delta_color="normal")
c[1].metric("7 days", fmt(stats["chg_7d"]), fmt(stats["chg_7d"]), delta_color="normal")
c[2].metric("30 days", fmt(stats["chg_30d"]), fmt(stats["chg_30d"]), delta_color="normal")
c[3].metric("30-day high", f"{stats['high30']:,.4f}")
c[4].metric("30-day low", f"{stats['low30']:,.4f}")
c[5].metric("30-day average", f"{stats['avg30']:,.4f}", f"today {(rate / stats['avg30'] - 1) * 100:+.2f}% vs avg")
st.progress(stats["pos52"], text=f"Position in the 1-year range: {stats['low52']:,.4f} (low) to {stats['high52']:,.4f} (high), "
                                 f"today at {stats['pos52'] * 100:.0f}%")

window = st.radio("Chart range", ["30 days", "90 days", "1 year"], index=0, horizontal=True)
days = {"30 days": 30, "90 days": 90, "1 year": 365}[window]
shown = series.loc[series.index >= series.index[-1] - pd.Timedelta(days=days)]
fig = go.Figure(go.Scatter(x=shown.index, y=shown, mode="lines", name=f"{base}/{target}", line=dict(width=2.5, color="#4a90e2"),
                           fill="tozeroy", fillcolor="rgba(74,144,226,0.08)"))
fig.add_hline(y=shown.mean(), line_dash="dot", line_color="#f5a623", annotation_text=f"{window} average")
fig.update_yaxes(range=[shown.min() * 0.995, shown.max() * 1.005])
fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified")
st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------- basket ----
st.subheader(f"{base} {money(amount, base)} in other currencies")
others = [cur for cur in CURRENCIES if cur != base]
picked = st.multiselect("Currencies to compare", others, default=others[:6])
rows = []
for cur in picked:
    s = history[cur].dropna()
    info = summarise(s)
    rows.append({
        "Currency": cur, "Rate": info["today"],
        f"You get ({fee:g}% fee)" if fee else "You get": amount * info["today"] * (1 - fee / 100),
        "7d": info["chg_7d"], "30d": info["chg_30d"], "Rate signal": rate_signal(info)[0],
    })
if rows:
    table = pd.DataFrame(rows)
    get_col = table.columns[2]
    table[get_col] = [money(v, cur) for v, cur in zip(table[get_col], table["Currency"])]
    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "Rate": st.column_config.NumberColumn(format="%.4f"),
            "7d": st.column_config.NumberColumn(format="%+.2f%%"),
            "30d": st.column_config.NumberColumn(format="%+.2f%%"),
        },
    )

# ----------------------------------------------------------------- footer ----
st.caption(
    f"Rates dated {stats['date']:%d %b %Y} (ECB reference rates via frankfurter.dev), fetched {loaded['fetched_at']}, "
    f"cached 1 hour. {market_note(stats['date'].date(), date.today())}"
)
st.info(
    "Mid-market rates are not what banks or money changers give you; use the fee selector to estimate the real cost. "
    "The signal only compares today's rate with its recent average. It is educational, **not financial advice**."
)
with st.expander("About"):
    st.markdown(
        """
- **Python libraries:** streamlit, pandas, plotly, requests
- **Data source:** [frankfurter.dev](https://frankfurter.dev) (European Central Bank reference rates, published on working days)
- **Pixel art:** made with [Pixelbolt](https://github.com/skulitom/Pixelbolt)
"""
    )

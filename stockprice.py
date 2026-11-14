import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Simple Stock Price App", layout="wide")

TICKERS = {
    "AAPL": "Apple, AAPL",
    "GOOGL": "Google, GOOGL",
    "MSFT": "Microsoft, MSFT",
    "SSNLF": "Samsung Electronics, SSNLF",
    "TM": "Toyota Motor, TM",
    "HMC": "Honda Motor Company, HMC",
    "NTDOY": "Nintendo, NTDOY",
    "ZM": "Zoom Video Communications, ZM",
}

# Sidebar
st.sidebar.header("Input Options")
ticker = st.sidebar.selectbox("Select ticker", list(TICKERS), format_func=TICKERS.get)
start_date = st.sidebar.date_input("Start date", value=pd.Timestamp("1990-01-01"))
end_date = st.sidebar.date_input("End date")

st.image("images/banner.gif", width=420)  # pixel art made with Pixelbolt
st.title("Simple Stock Price App")
st.write(f"Shown are the **closing price** and **volume** of {ticker}!")


@st.cache_data(ttl=3600)
def load_history(symbol, start, end) -> pd.DataFrame:
    return yf.Ticker(symbol).history(start=start, end=end)


if start_date >= end_date:
    st.error("Start date must be before end date.")
    st.stop()

try:
    history = load_history(ticker, start_date, end_date)
except Exception as err:  # yfinance raises various network/parse errors
    st.error(f"Could not load data from Yahoo Finance. ({err})")
    st.stop()

if history.empty:
    st.warning("No data found for this ticker and date range.")
    st.stop()

st.dataframe(history)

st.subheader("Closing Price")
st.line_chart(history["Close"])
st.subheader("Volume")
st.line_chart(history["Volume"])

st.download_button(
    "Download data as CSV",
    data=history.to_csv().encode("utf-8"),
    file_name=f"{ticker}.csv",
    mime="text/csv",
)

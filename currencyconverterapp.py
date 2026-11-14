import pandas as pd
import requests
import streamlit as st
from PIL import Image

st.set_page_config(page_title="Currency Converter", layout="wide")

API_URL = "https://api.frankfurter.dev/v1/latest"
CURRENCIES = ["JPY", "IDR", "MYR", "USD", "SGD", "KRW", "CNY"]

st.image(Image.open("images/img2.png"), width=300)
st.title("Currency Converter App")
st.markdown("This app converts the value of foreign currencies.")

# Sidebar
st.sidebar.header("Input Options")
amount = st.sidebar.number_input("Enter an amount", min_value=0.0, value=1.0, step=1.0)
base = st.sidebar.selectbox("Select base currency", CURRENCIES, index=CURRENCIES.index("USD"))
target = st.sidebar.selectbox("Select target currency", CURRENCIES, index=CURRENCIES.index("MYR"))


@st.cache_data(ttl=3600)
def load_rate(base: str, target: str) -> dict:
    """Fetch the latest rate from frankfurter.dev (free, no API key)."""
    response = requests.get(API_URL, params={"base": base, "symbols": target}, timeout=10)
    response.raise_for_status()
    return response.json()


st.header("Currency conversion")

if base == target:
    st.info("Base and target currency are the same. Pick two different currencies.")
else:
    try:
        data = load_rate(base, target)
        rate = data["rates"][target]
        st.dataframe(
            pd.DataFrame(
                [{"base_currency": data["base"], "converted_currency": target,
                  "price": rate, "date": data["date"]}]
            ),
            hide_index=True,
        )
        st.success(f"{base} {amount:,.2f}  ⇒  {target} {amount * rate:,.2f}")
    except (requests.RequestException, KeyError, ValueError) as err:
        st.error(f"Could not load exchange rates. Please try again later. ({err})")

with st.expander("About"):
    st.markdown(
        """
- **Python libraries:** streamlit, pandas, requests, pillow
- **Data source:** [frankfurter.dev](https://frankfurter.dev) (European Central Bank rates, updated on working days)
"""
    )

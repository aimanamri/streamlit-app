<p align="center">
  <img src="images/banner.gif" alt="Pixel-art stock chart animation" width="480">
</p>

# Streamlit Apps

Three small data apps built with [Streamlit](https://streamlit.io).

| | App | File | What it does | Libraries |
| --- | --- | --- | --- | --- |
| <img src="images/art-currency.gif" width="48"> | Currency Converter | `currencyconverterapp.py` | Converts between JPY, IDR, MYR, USD, SGD, KRW and CNY using live rates ([frankfurter.dev](https://frankfurter.dev), no API key) | streamlit, pandas, requests |
| <img src="images/banner.gif" width="96"> | Stock Analysis | `stockprice.py` | NASDAQ, Bursa Malaysia and Japan (Tokyo): candlestick charts, SMA/EMA, Bollinger, RSI, MACD, Stochastic, a rule-based buy/neutral/sell signal, comparison with earlier weeks, months and years, and Shariah status for Bursa stocks | streamlit, pandas, yfinance, plotly, pypdf |
| <img src="images/art-syllabus.gif" width="48"> | KIT Course Syllabus | `syllabusapp.py` | Reads every level, faculty, field and program live from [syllabus.kit.ac.jp](https://www.syllabus.kit.ac.jp/?c=menu&sk=00); filter by year, semester, day, period and title. Cached, with the last-fetched time shown | streamlit, pandas, requests, beautifulsoup4 |

| Currency Converter | Stock Price | KIT Syllabus |
| --- | --- | --- |
| ![Currency Converter](images/intro.gif) | ![Stock Price](images/intro2.gif) | ![KIT Syllabus](images/intro3.gif) |

## Stock Analysis app

- **Markets:** NASDAQ, Bursa Malaysia (`.KL`) and Japan (`.T`). Pick from the dropdown (type to search) or type any ticker or code, for example `AAPL`, `1155` or `7203`.
- **Default period:** the last year; 1M to 5Y or a custom range in the sidebar.
- **Signals tab:** each indicator votes bullish, neutral or bearish, and the weighted result is shown as Strong Buy, Buy, Neutral, Sell or Strong Sell, with support and resistance levels. This is a simple educational rule set, **not investment advice**.
- **Compare tab:** price now vs 1 week to 3 years ago, the selected period overlaid on the previous period or the same period 1 or 2 years earlier, and monthly and yearly returns.
- **Shariah status (Bursa Malaysia):** checked against the Securities Commission Malaysia list, with an optional "Only Shariah-compliant stocks" filter. A stock missing from the list may be non-compliant, newly listed, or an ETF/REIT, so verify at [sc.com.my](https://www.sc.com.my/development/icm/shariah-compliant-securities).

## Data files and parsers

The app ships with data files in `data/`, built by the scripts in `parsers/`:

| File | Source | Used for |
| --- | --- | --- |
| `data/shariah_my.json` | SC Malaysia list of Shariah-compliant securities (PDF, updated every May and November) | Shariah badge and filter |
| `data/tickers.json` | Nasdaq screener (NASDAQ), FTSE Bursa Malaysia KLCI + the Shariah list (Bursa), JPX listed-company workbook (Japan) | Stock dropdowns |

Refresh them by hand with:

```bash
pip install -r requirements-data.txt
python scripts/update_data.py            # everything
python scripts/update_data.py shariah    # or: tickers
```

A GitHub Action (`.github/workflows/update-data.yml`) runs this on the 1st and 15th of each month (and on demand from the Actions tab), then commits only if the data changed. If a source fails, its old file is kept and the run is marked failed so you notice. Because Streamlit Community Cloud redeploys on every push to `main`, a new Shariah list reaches the live app automatically. To add another market or data source, add a function in `parsers/` and a task in `scripts/update_data.py`. Tests (`pytest`) and a start-up check run on every push (`.github/workflows/ci.yml`).

## Run locally

Requires Python 3.9+.

```bash
git clone https://github.com/aimanamri/streamlit-app.git
cd streamlit-app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then start any one app:

```bash
streamlit run currencyconverterapp.py
streamlit run stockprice.py
streamlit run syllabusapp.py
```

It opens at http://localhost:8501.

## Deploy (Streamlit Community Cloud, free)

Each app is deployed separately from the same repo.

1. Push this repo to GitHub (it must contain `requirements.txt`, which it already does).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **Create app** and choose **Deploy a public app from GitHub**.
4. Fill in:
   - **Repository:** `aimanamri/streamlit-app`
   - **Branch:** `main`
   - **Main file path:** `currencyconverterapp.py` (or `stockprice.py`, `syllabusapp.py`)
5. Click **Deploy**. The first build takes a few minutes. You get a URL like `https://<your-app>.streamlit.app`.

Repeat steps 3-5 for each of the other apps.

Notes:
- Redeploys are automatic on every push to `main`, including the data refresh commits above.
- Free apps go to sleep after inactivity; visitors just click "wake up".
- Other options: [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-sdks-streamlit) (choose the Streamlit SDK) or any host that can run `streamlit run <file> --server.port $PORT --server.address 0.0.0.0` (Render, Railway, Fly.io).
- No secrets or API keys are needed.

## Credits

Pixel-art animations made with [Pixelbolt](https://github.com/skulitom/Pixelbolt).

## License

[MIT](LICENSE)

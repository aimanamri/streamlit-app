<p align="center">
  <img src="images/banner.gif" alt="Pixel-art stock chart animation" width="480">
</p>

# Streamlit Apps

Three small data apps built with [Streamlit](https://streamlit.io).

| | App | File | What it does | Libraries |
| --- | --- | --- | --- | --- |
| <img src="images/art-currency.gif" width="48"> | Currency Converter | `currencyconverterapp.py` | Converts between JPY, IDR, MYR, USD, SGD, KRW and CNY using live rates ([frankfurter.dev](https://frankfurter.dev), no API key) | streamlit, pandas, requests |
| <img src="images/banner.gif" width="96"> | Simple Stock Price | `stockprice.py` | Closing price and volume charts for a few tickers, with CSV download ([yfinance](https://github.com/ranaroussi/yfinance)) | streamlit, pandas, yfinance |
| <img src="images/art-syllabus.gif" width="48"> | KIT Course Syllabus | `syllabusapp.py` | Reads every level, faculty, field and program live from [syllabus.kit.ac.jp](https://www.syllabus.kit.ac.jp/?c=menu&sk=00); filter by year, semester, day, period and title. Cached, with the last-fetched time shown | streamlit, pandas, requests, beautifulsoup4 |

| Currency Converter | Stock Price | KIT Syllabus |
| --- | --- | --- |
| ![Currency Converter](images/intro.gif) | ![Stock Price](images/intro2.gif) | ![KIT Syllabus](images/intro3.gif) |

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
- Redeploys are automatic on every push to `main`.
- Free apps go to sleep after inactivity; visitors just click "wake up".
- Other options: [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-sdks-streamlit) (choose the Streamlit SDK) or any host that can run `streamlit run <file> --server.port $PORT --server.address 0.0.0.0` (Render, Railway, Fly.io).
- No secrets or API keys are needed.

## Credits

Pixel-art animations made with [Pixelbolt](https://github.com/skulitom/Pixelbolt).

## License

[MIT](LICENSE)

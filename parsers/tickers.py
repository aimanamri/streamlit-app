"""Ticker lists for the dropdowns: NASDAQ (official screener), Bursa Malaysia (FTSE KLCI + the
Shariah list) and Japan (JPX listed-company workbook)."""
import re
from io import BytesIO

import pandas as pd
from bs4 import BeautifulSoup

from .common import DATA_DIR, get, now_iso, read_json

OUTPUT = DATA_DIR / "tickers.json"
NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=15000&exchange=nasdaq&download=true"
KLCI_URL = "https://en.wikipedia.org/wiki/FTSE_Bursa_Malaysia_KLCI"
JPX_PAGE = "https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html"
MINIMUMS = {"NASDAQ": 2500, "Bursa Malaysia": 500, "Japan (Tokyo)": 3000}


class ParseError(Exception):
    pass


def clean_name(name: str) -> str:
    name = re.sub(r"\s+(Common Stock|Class [A-Z] (Common|Ordinary) (Stock|Shares)|Ordinary Shares|American Depositary Shares?.*)$", "", name.strip(), flags=re.I)
    return re.sub(r"\s+", " ", name)


def nasdaq() -> dict:
    rows = get(NASDAQ_URL, headers={"Accept": "application/json"}).json()["data"]["rows"]
    out = {r["symbol"].strip(): clean_name(r["name"]) for r in rows if r.get("symbol") and "^" not in r["symbol"]}
    skip = re.compile(r"warrant|\brights?\b|\bunits?\b|\bnotes?\b|preferred|depositary", re.I)
    return {k: v for k, v in out.items() if re.fullmatch(r"[A-Z]{1,5}", k) and not skip.search(v)}


def klci() -> dict:
    """FTSE Bursa Malaysia KLCI constituents: the table with 'Constituent Name' and 'Stock Code'."""
    soup = BeautifulSoup(get(KLCI_URL).text, "html.parser")
    for table in soup.find_all("table"):
        header = [c.get_text(" ", strip=True) for c in table.find("tr").find_all(["th", "td"])]
        if "Stock Code" in header and any("Name" in h for h in header):
            name_i = next(i for i, h in enumerate(header) if "Name" in h)
            code_i = header.index("Stock Code")
            out = {}
            for tr in table.find_all("tr")[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) > max(name_i, code_i) and re.fullmatch(r"\d{4}[A-Z]?", cells[code_i]):
                    out[cells[code_i]] = cells[name_i]
            if len(out) >= 20:
                return out
    raise ParseError("KLCI constituent table not found.")


def bursa(shariah: dict | None) -> dict:
    """KLCI plus every Shariah-compliant security (names from the SC list are as written there)."""
    out = dict((shariah or {}).get("securities", {}))
    out.update(klci())  # KLCI names are cleaner, so they win
    return out


def japan() -> dict:
    page = BeautifulSoup(get(JPX_PAGE).text, "html.parser")
    link = next((a["href"] for a in page.find_all("a", href=True) if a["href"].endswith("data_e.xlsx")), None)
    if not link:
        raise ParseError("JPX listed-company workbook link not found.")
    url = link if link.startswith("http") else "https://www.jpx.co.jp" + link
    df = pd.read_excel(BytesIO(get(url).content), dtype=str)
    code_col = next(c for c in df.columns if "Code" in c and "Sector" not in c)
    name_col = next(c for c in df.columns if "Name" in c)
    kind_col = next(c for c in df.columns if "Section" in c)
    df = df[df[kind_col].fillna("").str.contains("Market|ETF", regex=True)]
    return {c.strip(): n.strip() for c, n in zip(df[code_col], df[name_col]) if re.fullmatch(r"\d{3}[0-9A-Z]", c.strip())}


def build(shariah: dict | None) -> dict:
    old = (read_json(OUTPUT) or {}).get("markets", {})
    markets, errors = {}, {}
    for name, fn in (("NASDAQ", nasdaq), ("Bursa Malaysia", lambda: bursa(shariah)), ("Japan (Tokyo)", japan)):
        try:
            data = fn()
            if len(data) < MINIMUMS[name]:
                raise ParseError(f"only {len(data)} tickers (expected {MINIMUMS[name]}+)")
            markets[name] = {"count": len(data), "tickers": data}
        except Exception as err:  # keep the previous list for this market
            errors[name] = str(err)
            if name in old:
                markets[name] = old[name]
    if errors and not markets:
        raise ParseError(f"All ticker sources failed: {errors}")
    return {"generated_at": now_iso(), "markets": markets, "errors": errors}

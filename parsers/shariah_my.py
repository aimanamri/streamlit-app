"""Securities Commission Malaysia: list of Shariah-compliant securities (updated every May and November).

The SC site embeds the list of published PDFs as JSON in the page (newest first). We pick the
newest, download it and read the rows "12. 5347 Tenaga Nasional Bhd".
"""
import re
from io import BytesIO

from pypdf import PdfReader

from .common import DATA_DIR, get, now_iso

SC_PAGE = "https://www.sc.com.my/development/icm/shariah-compliant-securities/list-of-shariah-compliant-securities"
OUTPUT = DATA_DIR / "shariah_my.json"
MIN_SECURITIES = 500  # the list has ~860; far fewer means the layout changed

_ENTRY = re.compile(r'"name":"([^"]*)","file_path":"([^"]+)","date_published":"([^"]*)"')
_ROW = re.compile(r"(\d{1,3})\.\s+(\d{4,5}[A-Z]{0,2})\s+(.+?)(?=\s+\d{1,3}\.\s+\d{4,5}[A-Z]{0,2}\s|$)")


class ParseError(Exception):
    pass


def find_latest(page_html: str) -> dict:
    entry = _ENTRY.search(page_html)
    if not entry:
        raise ParseError("No published list found on the SC page (layout changed?).")
    return {"name": entry.group(1).strip(), "url": entry.group(2), "published": entry.group(3)}


def parse_text(text: str) -> dict:
    """{stock code: name} from extracted PDF text. Wrapped names keep only their first line."""
    securities = {}
    for line in text.splitlines():
        for _, code, name in _ROW.findall(line.strip()):
            securities[code] = name.strip()
    return securities


def parse_pdf(pdf_bytes: bytes) -> dict:
    securities = {}
    for page in PdfReader(BytesIO(pdf_bytes)).pages:
        securities.update(parse_text(page.extract_text() or ""))
    return securities


def build() -> dict:
    latest = find_latest(get(SC_PAGE).text)
    securities = parse_pdf(get(latest["url"]).content)
    if len(securities) < MIN_SECURITIES:
        raise ParseError(f"Only {len(securities)} securities parsed (expected 800+); not saving.")
    return {"source": SC_PAGE, "list_name": latest["name"], "published": latest["published"],
            "generated_at": now_iso(), "count": len(securities), "securities": securities}

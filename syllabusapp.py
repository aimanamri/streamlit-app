"""Web Syllabus App for Kyoto Institute of Technology (KIT).

Nothing is hard-coded about programs: the category tree (tab > faculty > field >
program) and the filter options (year, semester, day, period) are read from
https://www.syllabus.kit.ac.jp/?c=menu&sk=00 and its sibling tabs. Course tables
are read by matching column headers, not positions, so a changed column order or a
new program does not break the app. If the layout changes beyond recognition the
app says so instead of showing wrong data.
"""
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

BASE = "https://www.syllabus.kit.ac.jp/"
MENU_URL = BASE + "?c=menu&sk=00"
HEADERS = {"User-Agent": "Mozilla/5.0 (streamlit-syllabus-app; personal project)"}
JST = timezone(timedelta(hours=9))
CATALOG_TTL = 24 * 3600   # categories and filter options change rarely
COURSES_TTL = 6 * 3600
MAX_PAGES = 100           # safety stop

# Result-table column -> keywords looked for in the (Japanese + English) header cell.
COLUMNS = {
    "Timetable number": ["Timetable"],
    "Course": ["Course Title"],
    "Class": ["Class"],
    "Type": ["Course Type"],
    "Credits": ["Credits"],
    "Instructor": ["Instructor"],
    "Year": ["Year"],
    "Semester": ["Semester"],
    "Day & period": ["Day"],
    "Note": ["Note"],
}
# Refine-search selects on the menu page: GET parameter -> label shown in the sidebar.
FILTERS = {"an": "年次 / Year", "sm": "学期 / Semester", "wd": "曜日 / Day", "tt": "時限 / Period"}


class ScrapeError(Exception):
    """The site answered, but its HTML no longer looks like what we expect."""


def now_stamp() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")


def get_html(url: str, retries: int = 3) -> str:
    last = None
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except requests.RequestException as err:
            last = err
            time.sleep(1.5 * (attempt + 1))
    raise last


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("　", " ")).strip()


# ---------------------------------------------------------------- catalog ----
def parse_tabs(soup: BeautifulSoup) -> dict:
    """{sk: label} from the top tabs (Undergraduate / Master's / Doctoral / All)."""
    tabs = {}
    for a in soup.select('a[href*="c=menu"][href*="sk="]'):
        sk = parse_qs(urlparse(a["href"]).query).get("sk", [""])[0]
        if sk and "archive" not in a["href"] and a.find_parent("nav"):
            label = clean(a.get_text(" "))
            tabs[sk] = label
    return tabs


def parse_tree(soup: BeautifulSoup) -> list:
    """Every category link on a menu page as {label, dc, ac, sc, sk}."""
    nodes = []
    for a in soup.select('a[href*="c=search_list"]'):
        query = parse_qs(urlparse(a["href"]).query)
        node = {k: query.get(k, [""])[0] for k in ("sk", "dc", "ac", "sc")}
        node["label"] = clean(a.get_text(" "))
        if node["dc"] and node["label"]:
            nodes.append(node)
    return nodes


def parse_filters(soup: BeautifulSoup) -> dict:
    """{param: [(value, label), ...]} read from the refine-search selects."""
    found = {}
    for param in FILTERS:
        select = soup.find("select", attrs={"name": param})
        options = []
        if select:
            for option in select.find_all("option"):
                value, label = option.get("value", ""), clean(option.get_text(" "))
                if value and label:
                    options.append((value, label))
        found[param] = options
    return found


@st.cache_data(ttl=CATALOG_TTL, show_spinner="Reading the syllabus menu...")
def load_catalog() -> dict:
    home = soup_of(get_html(MENU_URL))
    tabs = parse_tabs(home) or {"00": "Undergraduate Programs"}
    filters = parse_filters(home)
    trees = {}
    for sk in tabs:
        page = home if sk == "00" else soup_of(get_html(f"{BASE}?c=menu&sk={sk}"))
        trees[sk] = parse_tree(page)
    if not any(trees.values()):
        raise ScrapeError("Could not find the category list on the menu page.")
    return {"tabs": tabs, "trees": trees, "filters": filters, "fetched_at": now_stamp()}


# ---------------------------------------------------------------- courses ----
def parse_results(soup: BeautifulSoup):
    """Return (total, rows) for one result page; raise ScrapeError on a layout we don't know."""
    text = soup.get_text(" ")
    if "見つかりませんでした" in text or "No results" in text:
        return 0, []
    total = re.search(r"(\d+)\s*件のレコード", text) or re.search(r"(\d+)\s+results", text)
    tables = soup.find_all("table", class_=re.compile(r"data_list_tbl"))
    if not tables or total is None:
        raise ScrapeError("The result table or record count was not found on the page.")

    # A page holds one table per category heading, so read them all.
    rows = []
    for table in tables:
        heading = table.find_previous_sibling("p", class_=re.compile(r"data_list_header"))
        category = clean(heading.get_text(" / ", strip=True)) if heading else ""
        header_cells = [clean(th.get_text(" ")) for th in table.find_all("th")]
        index = {}
        for name, keywords in COLUMNS.items():
            for i, header in enumerate(header_cells):
                if any(k.lower() in header.lower() for k in keywords):
                    index.setdefault(name, i)
                    break
        if "Course" not in index:
            raise ScrapeError(f"Column headers not recognised: {header_cells}")
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < len(header_cells) - 1 or tr.find("a") is None:
                continue
            row = {"Category": category}
            for name, i in index.items():
                if i < len(cells):
                    row[name] = clean(cells[i].get_text(" / ", strip=True))
            link = tr.find("a", href=True)
            row["Link"] = urljoin(BASE, link["href"])
            rows.append(row)
    return int(total.group(1)), rows


@st.cache_data(ttl=COURSES_TTL, show_spinner="Retrieving syllabus data from the KIT site...")
def load_courses(query: str) -> dict:
    """Fetch every page of one search. `query` is a urlencoded string so it can be a cache key."""
    rows, total = [], None
    for page in range(1, MAX_PAGES + 1):
        soup = soup_of(get_html(f"{BASE}?c=search_list&{query}&page={page}"))
        page_total, page_rows = parse_results(soup)
        total = total or page_total
        if not page_rows:
            break
        rows += page_rows
        if len(rows) >= total:
            break
        time.sleep(0.2)  # be polite to a university server
    df = pd.DataFrame(rows)
    if not df.empty:
        if "Credits" in df:
            df["Credits"] = pd.to_numeric(df["Credits"], errors="coerce")
        df.index = range(1, len(df) + 1)
    if total is not None and len(rows) != total:
        st.session_state["count_mismatch"] = (len(rows), total)
    return {"df": df, "total": total or 0, "fetched_at": now_stamp()}


# --------------------------------------------------------------------- UI ----
st.set_page_config(page_title="Web Syllabus App", layout="wide")
art, head = st.columns([1, 6], vertical_alignment="center")
art.image("images/art-syllabus.gif", width=96)  # pixel art made with Pixelbolt
head.write("# Web Syllabus App\n### Kyoto Institute of Technology (KIT)")

try:
    catalog = load_catalog()
except (requests.RequestException, ScrapeError) as err:
    st.error(f"Could not read the KIT syllabus menu. Please try again later. ({err})")
    st.markdown(f"[Open the official site]({MENU_URL})")
    st.stop()

st.sidebar.header("Search")
tab_keys = list(catalog["tabs"])
sk = st.sidebar.selectbox(
    "区分 / Level", tab_keys, index=tab_keys.index("00") if "00" in tab_keys else 0,
    format_func=lambda k: catalog["tabs"][k],
)
nodes = catalog["trees"][sk]

faculties = [n for n in nodes if not n["ac"] and not n["sc"]]
faculty = st.sidebar.selectbox("学部等 / Faculty", faculties, format_func=lambda n: n["label"]) if faculties else None
dc = faculty["dc"] if faculty else nodes[0]["dc"]
in_faculty = [n for n in nodes if n["dc"] == dc]

# Fields: from their own links when present, else from the codes the program links carry.
field_label = {n["ac"]: n["label"] for n in in_faculty if n["ac"] and not n["sc"]}
for n in in_faculty:
    if n["ac"] and n["ac"] not in field_label:
        field_label[n["ac"]] = None
ac_choice = st.sidebar.selectbox(
    "学域等 / Field",
    [""] + list(field_label),
    format_func=lambda a: "(all)" if a == "" else (field_label[a] or f"Field {a}"),
)
programs = [n for n in in_faculty if n["sc"] and (not ac_choice or n["ac"] == ac_choice)]
program = None
if programs:
    program = st.sidebar.selectbox(
        "課程等 / Program",
        [None] + programs,
        format_func=lambda n: "(all)" if n is None else n["label"],
    )

params = {"sk": sk, "dc": dc}
if ac_choice:
    params["ac"] = ac_choice
if program:
    params.update(ac=program["ac"], sc=program["sc"])

for param, label in FILTERS.items():
    options = catalog["filters"].get(param, [])
    if options:
        labels = dict(options)
        value = st.sidebar.selectbox(label, [""] + list(labels), format_func=lambda v, d=labels: "(all)" if v == "" else d[v])
        if value:
            params[param] = value

text_filter = st.sidebar.text_input("Course name contains")

if st.sidebar.button("Refresh data from the site"):
    st.cache_data.clear()
    st.rerun()

narrowed = bool(ac_choice or program or any(p in params for p in FILTERS))
if not narrowed and not st.sidebar.checkbox("Load the whole faculty (about a minute the first time)"):
    st.info("Pick a field, program or filter in the sidebar to load courses, or tick 'Load the whole faculty'.")
    st.caption(f"Menu fetched: {catalog['fetched_at']} (cached up to {CATALOG_TTL // 3600} h)")
    st.stop()

st.session_state.pop("count_mismatch", None)
try:
    result = load_courses(urlencode(params))
except requests.RequestException as err:
    st.error(f"Could not reach the KIT syllabus site. Please try again later. ({err})")
    st.stop()
except ScrapeError as err:
    st.error(
        "The syllabus site's layout seems to have changed, so the table could not be read. "
        f"({err})"
    )
    st.markdown(f"[Open this search on the official site]({BASE}?c=search_list&{urlencode(params)})")
    st.stop()

df = result["df"]
if text_filter and not df.empty:
    df = df[df["Course"].str.contains(text_filter, case=False, na=False)]

if df.empty:
    st.warning("No courses match the selected conditions.")
else:
    st.caption(f"{len(df)} courses")
    st.dataframe(
        df,
        width="stretch",
        column_config={"Link": st.column_config.LinkColumn("Details", display_text="open")},
    )
    st.download_button("Download as CSV", df.to_csv().encode("utf-8-sig"), "kit_syllabus.csv", "text/csv")

if "count_mismatch" in st.session_state:
    got, total = st.session_state["count_mismatch"]
    st.warning(f"The site reports {total} courses but only {got} were read; the page layout may have changed.")

st.caption(
    f"Course data fetched: {result['fetched_at']} (cached up to {COURSES_TTL // 3600} h) · "
    f"Menu fetched: {catalog['fetched_at']} (cached up to {CATALOG_TTL // 3600} h)"
)

with st.expander("About"):
    st.markdown(
        """
Categories and filters are read live from the KIT web syllabus, so new programs appear automatically.
- **Python libraries:** streamlit, pandas, requests, beautifulsoup4
- **Data source:** [syllabus.kit.ac.jp](https://www.syllabus.kit.ac.jp/?c=menu&sk=00)
"""
    )

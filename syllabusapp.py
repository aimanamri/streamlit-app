import re

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="Web Syllabus App", layout="wide")

PROGRAMS = {
    "機械工学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=05&sc=040&page=",
    "情報工学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=05&sc=037&page=",
    "電子システム工学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=05&sc=036&page=",
    "デザイン経営工学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=05&sc=039&page=",
    "デザイン・建築学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=06&sc=041&page=",
    "応用化学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=08&sc=032&page=",
    "応用生物学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=04&sc=032&page=",
    "高分子機能工学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=04&sc=034&page=",
    "物質工学課程": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=04&sc=035&page=",
    "留学生科目": "https://www.syllabus.kit.ac.jp/?c=search_list&sk=00&dc=01&ac=11&page=",
}
MAX_PAGES = 20

# Sidebar
program = st.sidebar.selectbox("課程 / Program", list(PROGRAMS))
years = st.sidebar.multiselect("年次 / Year", [1, 2, 3, 4])
semesters = st.sidebar.multiselect("学期 / Semester", ["前期", "後期", "第1ｸｫｰﾀ", "第2ｸｫｰﾀ", "通年"])

st.write("# Web Syllabus App\n### Kyoto Institute of Technology (KIT)")


def first_part(text: str) -> str:
    """Keep the Japanese part of a title (drop the English translation)."""
    return re.split(r"([a-zA-Z]+)", text)[0].strip()


@st.cache_data(ttl=6 * 3600, show_spinner="Retrieving syllabus data...")
def load_courses(base_url: str) -> pd.DataFrame:
    rows = []
    for page in range(1, MAX_PAGES + 1):
        response = requests.get(f"{base_url}{page}", timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        table = soup.find("table", class_="gen_tbl2 data_list_tbl")
        if table is None:
            break
        page_rows = 0
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 8 or tr.a is None:
                continue
            try:
                credits = int(cells[4].text)
            except ValueError:
                continue
            rows.append({
                "Timetable number": cells[0].text.strip(),
                "Course name": first_part(tr.a.text),
                "Credits": credits,
                "Year": cells[6].text.strip()[:1],
                "Semester": first_part(cells[7].text),
            })
            page_rows += 1
        if page_rows == 0:  # ran past the last page
            break
    df = pd.DataFrame(rows, columns=["Timetable number", "Course name", "Credits", "Year", "Semester"])
    df.index += 1
    return df


try:
    courses = load_courses(PROGRAMS[program])
except requests.RequestException as err:
    st.error(f"Could not reach the KIT syllabus site. Please try again later. ({err})")
    st.stop()

if years:
    courses = courses[courses["Year"].isin([str(y) for y in years])]
if semesters:
    courses = courses[courses["Semester"].isin(semesters)]

if courses.empty:
    st.warning("No courses match the selected filters.")
else:
    st.caption(f"{len(courses)} courses")
    st.dataframe(courses, width="stretch")

with st.expander("About"):
    st.markdown(
        """
Shows the courses of the program you select, filterable by year and semester.
- **Python libraries:** streamlit, pandas, requests, beautifulsoup4, lxml
- **Data source:** [syllabus.kit.ac.jp](https://www.syllabus.kit.ac.jp/?c=menu&sk=00)
"""
    )

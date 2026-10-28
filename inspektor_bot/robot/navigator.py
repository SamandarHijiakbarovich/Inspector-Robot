"""Hisobotlar ro'yxati sahifasi: tabni tanlash, jadvalni o'qish, sahifalash."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.sync_api import Locator, Page

from ..config import Settings
from ..validator.models import ReportMeta
from . import selectors as S
from .auth import goto

log = logging.getLogger(__name__)

# Sarlavha emas, mazmun bo'yicha aniqlanadigan ustunlar (sarlavha siljisa ham ishlaydi)
INN_RE = re.compile(r"^(\d{9}|\d{14})$")  # STIR yoki JShShIR
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Sahifada ikkita jadval bor: ko'rinadigan #ci-root jadvali va eski, bo'sh, yashirin jadval.
# Avval aniq selektor bo'yicha, topilmasa ko'rinib turgan "STIR" li jadval bo'yicha qidiramiz.
_READ_TABLE_JS = """
(selector) => {
  const norm = s => (s || "").replace(/\\s+/g, " ").trim();
  const tables = Array.from(document.querySelectorAll("table"));
  let ti = tables.indexOf(document.querySelector(selector));
  if (ti < 0) {
    ti = tables.findIndex(t => t.offsetParent !== null
      && /STIR/i.test(norm((t.tHead || t).innerText).slice(0, 600)));
  }
  if (ti < 0) return {tableIndex: -1, headers: [], rows: []};
  const t = tables[ti];
  const headCells = t.tHead ? Array.from(t.tHead.querySelectorAll("th,td")) : Array.from(t.rows[0].cells);
  const bodyRows = t.tBodies.length ? Array.from(t.tBodies[0].rows) : Array.from(t.rows).slice(1);
  return {
    tableIndex: ti,
    headers: headCells.map(c => norm(c.innerText)),
    rows: bodyRows.map(r => Array.from(r.cells).map(c => norm(c.innerText))),
  };
}
"""


@dataclass
class ListRow:
    index: int
    form_type: str
    form_label: str
    inn: str
    org_name: str
    opf: str
    submitted_at: str
    soato: str
    inspector: str
    status: str
    cells: list[str]

    @property
    def key(self) -> str:
        return f"{self.form_type}:{self.inn}:{self.submitted_at}"

    def to_meta(self) -> ReportMeta:
        return ReportMeta(
            form_type=self.form_type, form_label=self.form_label, inn=self.inn,
            org_name=self.org_name, opf=self.opf, soato=self.soato,
            submitted_at=self.submitted_at, status=self.status,
        )


class ReportList:
    def __init__(self, page: Page, settings: Settings):
        self.page = page
        self.settings = settings
        self.form_type = ""
        self.page_no = 1
        self._table_index = -1

    def open(self, form_type: str, tab: str = "new") -> None:
        self.form_type = form_type
        self.page_no = 1
        goto(self.page, self.settings, self.settings.reports_url(form_type))
        if "/reports" not in urlparse(self.page.url).path:
            raise RuntimeError(f"Hisobotlar sahifasi ochilmadi, sayt boshqa sahifaga yo'naltirdi: {self.page.url}")
        self.page.locator(S.LIST_TABLE).first.wait_for()
        selector = S.TABS.get(tab)
        tab_el = self.page.locator(selector).first if selector else None
        if tab_el is not None and tab_el.count():
            tab_el.click()
        else:
            log.warning("'%s' tabi topilmadi, joriy ro'yxat bilan ishlanadi", tab)
        self.wait_loaded()

    def wait_loaded(self, timeout_s: float = 30) -> None:
        """"Yuklanmoqda…" yozuvi yo'qolguncha (ro'yxat AJAX bilan kelguncha) kutadi."""
        self.page.wait_for_timeout(500)  # tab bosilgach yuklash boshlanishiga vaqt
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            placeholder = self.page.locator(S.LIST_PLACEHOLDER)
            if not placeholder.count():
                return  # qatorlar chiqdi
            if "yuklanmoqda" not in placeholder.first.inner_text().lower():
                return  # "hisobot yo'q" kabi bo'sh ro'yxat xabari
            self.page.wait_for_timeout(400)
        log.warning("Ro'yxat %s soniyada yuklanmadi", timeout_s)

    def read_rows(self) -> list[ListRow]:
        data = self.page.evaluate(_READ_TABLE_JS, S.LIST_TABLE)
        self._table_index = data["tableIndex"]
        headers = [h.lower() for h in data["headers"]]
        rows: list[ListRow] = []
        for i, cells in enumerate(data["rows"]):
            inn_idx = next((k for k, c in enumerate(cells) if INN_RE.match(c)), None)
            if inn_idx is None:
                continue  # bo'sh qator / "ma'lumot yo'q"
            # Sarlavha va qator katakchalari orasidagi siljishni INN ustuni bo'yicha aniqlaymiz
            head_inn = next((k for k, h in enumerate(headers) if "stir" in h), inn_idx)
            offset = inn_idx - head_inn

            def col(word: str) -> str:
                k = next((k for k, h in enumerate(headers) if word in h), None)
                if k is None or not 0 <= k + offset < len(cells):
                    return ""
                return cells[k + offset]

            date = next((c for c in cells if DATE_RE.search(c)), "")
            rows.append(ListRow(
                index=i, form_type=self.form_type, form_label=col("shakl"),
                inn=cells[inn_idx], org_name=col("tashkilot"), opf=col("opf"),
                submitted_at=date, soato=col("soato"), inspector=col("inspektor"),
                status=col("holati"), cells=cells,
            ))
        return rows

    def row_locator(self, row: ListRow) -> Locator:
        return self.page.locator("table").nth(self._table_index).locator("tbody tr").nth(row.index)

    def _first_row_text(self) -> str:
        row = self.page.locator(S.LIST_TABLE).locator("tbody tr").first
        return row.inner_text() if row.count() else ""

    def next_page(self) -> bool:
        """Pastdagi « 1 2 3 » sahifalagichda keyingi raqamni bosadi. Keyingi sahifa bo'lmasa False.

        "»" ga emas, raqamga tayanamiz: oxirgi sahifada "»" qanday o'chirilishi noma'lum,
        raqam esa yo bor, yo yo'q.
        """
        target = str(self.page_no + 1)
        pager = self.page.locator(S.LIST_PAGER).first
        if not pager.count():
            return False
        btn = pager.get_by_text(target, exact=True).first
        if not btn.count():
            nxt = self.page.locator(S.NEXT_PAGE).first  # raqamlar ko'rinmasa - "»" tugmasi
            if not nxt.count():
                return False
            btn = nxt
        before = self._first_row_text()
        btn.click()
        self.wait_loaded()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and self._first_row_text() == before:
            self.page.wait_for_timeout(300)
        if self._first_row_text() == before:
            log.warning("%s-sahifaga o'tib bo'lmadi (ro'yxat o'zgarmadi)", target)
            return False
        self.page_no += 1
        log.info("%s-sahifaga o'tildi", self.page_no)
        return True

    def goto_page(self, number: int) -> None:
        """Ro'yxat qayta yuklangandan keyin avvalgi sahifaga qaytish."""
        while self.page_no < number and self.next_page():
            pass

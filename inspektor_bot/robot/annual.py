"""Yillik moliyaviy hisobotni (1-fx shakli, form 602) STIR bo'yicha ochish va o'qish.

Inspektorning qo'lda bajaradigan tartibi (foydalanuvchi bergan):
  1. STIR olinadi.
  2. logotip bosiladi -> /uz/inspector/
  3. "Barchasi" -> /uz/inspector/reports/all
  4. STIR qo'yiladi, "1 fx shakli / Yillik" qatori topiladi, STIR bosiladi -> hisobot ochiladi.
  5. II-bo'lim 6-bob 19-§, 7-bob 20-§, 21-§ bo'limlari ko'riladi.
  6. 685-hisobot bilan solishtiriladi.

MUHIM: yillik hisobot "ming so'm"da, 685 "mln so'm"da. Solishtirishda 1000 ga bo'linadi.
Bu modul HALI KALIBRLANMAGAN - avval dump_annual() bilan haqiqiy sahifa saqlanadi.
"""
from __future__ import annotations

import logging
import re

from playwright.sync_api import Page

from ..config import Settings
from .auth import goto

log = logging.getLogger(__name__)

# Qaysi hisobot yillik moliyaviy ("1-fx shakli", "1 fx shakli", "1-fx" ...)
ANNUAL_NAME_RE = re.compile(r"1[\s\-]*fx", re.I)
ANNUAL_PERIOD_RE = re.compile(r"yillik", re.I)
# Solishtiriladigan bo'limlar (tab matnidan qidiriladi)
SECTION_TABS = ("19-§", "20-§", "21-§")

# Jadvalni o'qish: har bir qatorda "Satr kodi" (B ustuni) va qiymat(lar).
# Qiymatlar <input> ichida bo'ladi, shuning uchun input.value ni ham olamiz.
_READ_SATR_JS = r"""
() => {
  const val = c => {
    const inp = c.querySelector('input, textarea');
    const t = inp ? (inp.value || '') : (c.innerText || '');
    return t.replace(/\s+/g, ' ').trim();
  };
  const out = [];
  for (const t of document.querySelectorAll('table')) {
    const head = (t.tHead || t).innerText || '';
    if (!/satr\s*kodi/i.test(head)) continue;
    const rows = (t.tBodies[0] ? [...t.tBodies[0].rows] : [...t.rows]);
    for (const r of rows) {
      const cells = [...r.cells].map(val);
      out.push(cells);
    }
  }
  return out;
}
"""


_ROW_TEXTS_JS = r"""
() => [...document.querySelectorAll('table tbody tr')]
  .map(r => (r.innerText || '').replace(/\s+/g, ' ').trim())
"""


def open_all_list(page: Page, settings: Settings, inn: str) -> None:
    """"Barchasi" ro'yxatini ochib, STIR bo'yicha filtrlaydi (bir marta)."""
    goto(page, settings, settings.all_reports_url)
    stir_filter = page.get_by_placeholder(re.compile(r"stir", re.I)).first
    if stir_filter.count():
        stir_filter.fill(inn)
        stir_filter.press("Enter")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
    else:
        log.warning("STIR filtri topilmadi - butun ro'yxatdan qidiriladi")


def row_texts(page: Page) -> list[str]:
    """Jadval qatorlarini bitta JS chaqiruvida o'qiydi (birma-bir o'qish qotib qolmasin)."""
    return page.evaluate(_ROW_TEXTS_JS)


def find_annual_index(texts: list[str], inn: str) -> int | None:
    """1-fx + Yillik + STIR mos keladigan BIRINCHI (eng yangi) qator indeksi."""
    for i, t in enumerate(texts):
        if inn in t and ANNUAL_NAME_RE.search(t) and ANNUAL_PERIOD_RE.search(t):
            return i
    return None


def click_stir(page: Page, index: int, inn: str) -> None:
    """Berilgan qatordagi STIR raqamining havolasiga bosadi va yangi sahifani kutadi."""
    row = page.locator("table tbody tr").nth(index)
    target = row.locator("a", has_text=inn).first
    if not target.count():
        target = row.get_by_text(inn, exact=True).first
    if not target.count():
        target = row.locator("a").first
    before = page.url
    target.click()
    try:
        page.wait_for_url(lambda u: u != before, timeout=15000)
    except Exception:
        page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)


def open_annual_report(page: Page, settings: Settings, inn: str) -> bool:
    """STIR bo'yicha yillik 1-fx hisobotini ochadi. Topilsa True."""
    open_all_list(page, settings, inn)
    index = find_annual_index(row_texts(page), inn)
    if index is None:
        log.warning("STIR %s uchun yillik 1-fx/Yillik qatori topilmadi", inn)
        return False
    click_stir(page, index, inn)
    log.info("Yillik 1-fx hisoboti ochildi: %s", page.url)
    return True


def read_section(page: Page, tab_label: str) -> list[list[str]]:
    """Bo'lim tabini bosib, uning Satr-kodli jadvalini qatorma-qator o'qiydi."""
    tab = page.get_by_text(tab_label, exact=False).first
    if tab.count():
        tab.click()
        page.wait_for_timeout(800)
    return page.evaluate(_READ_SATR_JS)


def read_annual(page: Page, settings: Settings, inn: str) -> dict[str, dict]:
    """Yillik hisobotni ochib, kerakli bo'limlarning Satr kodi -> qiymat jadvalini qaytaradi.

    Natija: {"20-§": {"1501": ["...", "90000.0", ...], ...}, "21-§": {...}}
    """
    if not open_annual_report(page, settings, inn):
        return {}
    result: dict[str, dict] = {}
    for tab in SECTION_TABS:
        rows = read_section(page, tab)
        by_code: dict[str, list[str]] = {}
        for cells in rows:
            code = next((c for c in cells if re.fullmatch(r"\d{3,4}(\.\d+)?", c)), None)
            if code:
                by_code[code] = cells
        result[tab] = by_code
    return result

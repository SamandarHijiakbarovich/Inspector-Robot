"""Kalibrlash: ro'yxat va birinchi hisobot oynasini faylga saqlaydi. HECH QANDAY TUGMA BOSILMAYDI.

Natijadagi modal.txt ni ko'rib, parser savollarni to'g'ri ajratganini (parsed.json)
va selektorlar ishlashini tekshirasiz.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from ..config import Settings
from ..parsing import parse_report
from ..validator import validate
from .auth import ensure_session
from .browser import open_browser
from .navigator import ReportList
from . import selectors as S
from .report_modal import ReportModal


API_MARKERS = ("/business/api/", "/v1/")


def _capture_api(page, store: list) -> None:
    """Sayt JavaScript'i yuklaydigan JSON javoblarni yozib boradi (ma'lumot modelini o'rganish uchun)."""
    def on_response(response):
        if not any(m in response.url for m in API_MARKERS):
            return
        try:
            body = response.json()
        except Exception:
            return
        store.append({"url": response.url, "method": response.request.method,
                      "status": response.status, "body": body})
    page.on("response", on_response)


def dump(settings: Settings, form_type: str, tab: str = "new", row_number: int = 1) -> Path:
    out = settings.dump_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    api: list[dict] = []
    with open_browser(settings) as page:
        ensure_session(page, settings)
        _capture_api(page, api)
        lst = ReportList(page, settings)
        lst.open(form_type, tab)
        page.screenshot(path=str(out / "list.png"), full_page=True)
        (out / "list.html").write_text(page.content(), encoding="utf-8")
        pager = page.locator(S.LIST_PAGER).first
        if pager.count():
            (out / "pager.html").write_text(pager.inner_html(), encoding="utf-8")
        rows = lst.read_rows()
        (out / "rows.json").write_text(
            json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Ro'yxatda {len(rows)} ta qator o'qildi")

        if rows:
            row = rows[min(row_number, len(rows)) - 1]
            modal = ReportModal(page, settings)
            modal.open_from_row(lst.row_locator(row))
            text = modal.read_text()
            modal.root.screenshot(path=str(out / "modal.png"))
            (out / "modal.txt").write_text(text, encoding="utf-8")
            (out / "modal.html").write_text(modal.html(), encoding="utf-8")
            report = parse_report(text, row.to_meta())
            result = validate(report, **settings.validate_kwargs())
            (out / "parsed.json").write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            (out / "result.json").write_text(json.dumps({
                "decision": result.decision.value,
                "comment": result.comment,
                "findings": [f.to_dict() for f in result.findings],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Hisobot: {row.org_name} ({row.inn}) -> {len(report.items)} ta savol, "
                  f"qaror: {result.decision.value}")
            page.wait_for_timeout(1000)
            modal.close()
    (out / "api.json").write_text(json.dumps(api, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"API javoblari: {len(api)} ta ({', '.join(sorted({a['url'].split('?')[0] for a in api})) or '-'})")
    print(f"Saqlandi: {out}")
    return out


def dump_annual(settings: Settings, inn: str) -> Path:
    """Yillik 1-fx hisobotini STIR bo'yicha ochib, 19/20/21-§ bo'limlarini faylga saqlaydi.

    Har qanday xatolikda ham joriy sahifani (HTML + skrinshot) saqlaydi, shunda
    kalibrlash uchun ko'rish mumkin bo'ladi.
    """
    import re as _re
    import traceback

    from . import annual as A

    out = settings.dump_dir / f"annual_{inn}_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)

    def snap(name: str, page) -> None:
        try:
            (out / f"{name}.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(out / f"{name}.png"), full_page=True)
            print(f"  saqlandi: {name} ({page.url})")
        except Exception as exc:
            print(f"  {name} saqlanmadi: {exc!r}")

    with open_browser(settings) as page:
        try:
            ensure_session(page, settings)
            # 1) "Barchasi" ro'yxati - STIR bo'yicha filtr (bir marta)
            A.open_all_list(page, settings, inn)
            snap("02_filtered", page)
            texts = A.row_texts(page)
            (out / "rows.txt").write_text("\n".join(texts), encoding="utf-8")
            print(f"  ro'yxatda {len(texts)} ta qator")

            # 2) Yillik 1-fx/Yillik qatorini topib, STIR havolasiga bosamiz
            index = A.find_annual_index(texts, inn)
            if index is None:
                snap("03_not_found", page)
                print(f"STIR {inn} uchun yillik 1-fx/Yillik qatori topilmadi. rows.txt ni ko'ring.")
                return out
            print(f"  topildi: {index + 1}-qator")
            A.click_stir(page, index, inn)
            snap("03_report_open", page)
            (out / "report_url.txt").write_text(page.url, encoding="utf-8")

            # 3) Bo'limlarni o'qish
            parsed: dict[str, dict] = {}
            for tab in A.SECTION_TABS:
                safe = tab.replace("§", "section").replace("-", "_")
                try:
                    rows = A.read_section(page, tab)
                except Exception as exc:
                    print(f"  {tab} o'qilmadi: {exc!r}")
                    rows = []
                snap(f"04_{safe}", page)
                by_code = {}
                for cells in rows:
                    code = next((c for c in cells if _re.fullmatch(r"\d{3,4}(\.\d+)?", c)), None)
                    if code:
                        by_code[code] = cells
                parsed[tab] = by_code
                print(f"  {tab}: {len(by_code)} ta satr kodi")
            (out / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            (out / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            snap("99_error", page)
            print("Xatolik yuz berdi - error.txt va 99_error.png saqlandi.")
    print(f"Saqlandi: {out}")
    return out

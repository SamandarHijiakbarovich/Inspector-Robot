"""Robotning asosiy ish sikli: ro'yxat -> hisobot -> tahlil -> qaror -> tugma -> log."""
from __future__ import annotations

import logging
import time
from typing import Callable

from playwright.sync_api import Page

from ..config import Settings
from ..parsing import parse_report
from ..storage import Database
from ..validator import Decision, validate
from ..validator.site_check import site_check_warnings
from .auth import ensure_session
from .browser import human_pause, open_browser
from .navigator import ListRow, ReportList
from .report_modal import ReportModal

log = logging.getLogger(__name__)

# (qaror, izoh matni, sayt "Tekshirish" matni) -> "ha" | "yo'q" | "q"
ConfirmFn = Callable[[Decision, str, str], str]


class Robot:
    def __init__(self, settings: Settings, db: Database,
                 confirm: ConfirmFn | None = None, out: Callable[[str], None] = print):
        """confirm - tasdiq so'rash usuli (oyna uchun); berilmasa terminalda so'raladi.
        out - natijalarni chiqarish usuli (terminal yoki oyna logi)."""
        self.s = settings
        self.db = db
        self.confirm = confirm
        self.out = out
        self.run_id: int | None = None
        self.counters: dict[str, int] = {}
        self.actions_done = 0
        self.seen: set[str] = set()
        self.stop_requested = False

    def request_stop(self) -> None:
        """Joriy hisobot tugagach robotni to'xtatish (oynadagi "To'xtatish" tugmasi)."""
        self.stop_requested = True

    # ---------- log ----------

    def _log(self, level: str, message: str, key: str | None = None) -> None:
        getattr(log, level.lower(), log.info)(("[%s] " % key if key else "") + message)
        self.db.log(self.run_id, level.upper(), message, key)

    def _count(self, name: str) -> None:
        self.counters[name] = self.counters.get(name, 0) + 1

    # ---------- asosiy sikl ----------

    def run_once(self) -> dict:
        self.run_id = self.db.start_run(self.s.mode)
        self.counters, self.actions_done, self.seen, self.stop_requested = {}, 0, set(), False
        note = ""
        self._log("INFO", f"Ishga tushdi. Rejim: {self.s.mode}, shakllar: {', '.join(self.s.form_types)}")
        try:
            with open_browser(self.s) as page:
                ensure_session(page, self.s)
                for form_type in self.s.form_types:
                    for tab in self.s.tabs:
                        self._process_list(page, form_type, tab)
                        if self._limit_reached():
                            break
        except Exception as exc:
            note = repr(exc)
            self._log("ERROR", f"Ish to'xtadi: {exc!r}")
        finally:
            self.db.finish_run(self.run_id, self.counters, note)
            self._log("INFO", f"Tugadi: {self.counters}")
        return self.counters

    def run_forever(self, interval_s: int) -> None:
        while True:
            self.run_once()
            self._log("INFO", f"Keyingi tekshiruv {interval_s} soniyadan keyin")
            time.sleep(interval_s)

    def _limit_reached(self) -> bool:
        if self.stop_requested:
            return True
        reviewed = self.counters.get("processed", 0) + self.counters.get("failed", 0)
        if self.s.max_reports and reviewed >= self.s.max_reports:
            return True
        return self.s.is_live and self.actions_done >= self.s.max_actions_per_run

    def _process_list(self, page: Page, form_type: str, tab: str) -> None:
        lst = ReportList(page, self.s)
        lst.open(form_type, tab)
        announced_page = 0
        while not self._limit_reached():
            rows = lst.read_rows()
            todo = [r for r in rows if r.key not in self.seen and not self.db.is_final(r.key)
                    and (not self.s.only_inn or r.inn == self.s.only_inn)]
            if announced_page != lst.page_no:
                announced_page = lst.page_no
                self._log("INFO", f"{lst.page_no}-sahifa: {len(rows)} ta hisobot, "
                                  f"ko'rilmagani {len(todo)} ta")
                if lst.page_no == 1 and not rows:
                    self._log("WARNING", f"Ro'yxatda hisobot topilmadi (shakl {form_type}, tab {tab}, "
                                         f"sahifa {page.url}). `python main.py dump` bilan tekshiring.")
            if not todo:
                # Bu sahifadagi hammasi ko'rildi - keyingi sahifaga
                if lst.next_page():
                    continue
                self._log("INFO", f"Ro'yxat tugadi ({lst.page_no} ta sahifa ko'rildi)")
                if self.s.only_inn and not self.counters.get("processed"):
                    self._log("WARNING", f"STIR {self.s.only_inn} bu ro'yxatda topilmadi")
                break
            row = todo[0]
            self.seen.add(row.key)
            acted = self._process_row(page, lst, row)
            human_pause(self.s)
            if acted:
                # Qabul/rad qilingan hisobot YANGI ro'yxatidan chiqib ketishi kerak -
                # ro'yxatni qayta yuklab, shuni TEKSHIRAMIZ, keyin shu sahifaga qaytamiz
                current = lst.page_no
                lst.open(form_type, tab)
                self._verify_left_list(lst, row)
                lst.goto_page(current)

    def _verify_left_list(self, lst: ReportList, row: ListRow) -> None:
        """Amaldan keyin hisobot YANGI ro'yxatida qolmaganini tekshiradi (1-sahifada)."""
        still = any(r.key == row.key for r in lst.read_rows())
        if still:
            self._log("WARNING", f"«{row.org_name}» amaldan keyin ham ro'yxatda turibdi — "
                      f"amal saytda saqlanmagan bo'lishi mumkin. Saytda qo'lda tekshiring.", row.key)
            self.db.log(self.run_id, "WARNING", "amal_tasdiqlanmadi", row.key)

    # ---------- bitta hisobot ----------

    def _process_row(self, page: Page, lst: ReportList, row: ListRow) -> bool:
        """True qaytarsa - saytda holat o'zgartiruvchi amal bajarildi."""
        key = row.key
        modal = ReportModal(page, self.s)
        record = {
            "report_key": key, "run_id": self.run_id, "form_type": row.form_type, "inn": row.inn,
            "org_name": row.org_name, "opf": row.opf, "soato": row.soato, "submitted_at": row.submitted_at,
        }
        acted = False
        try:
            modal.open_from_row(lst.row_locator(row))
            text = modal.read_text()
            report = parse_report(text, row.to_meta())
            result = validate(report, **self.s.validate_kwargs())
            record.update(
                decision=result.decision.value, comment=result.comment, raw_text=text,
                findings=[f.to_dict() for f in result.findings], data=report.to_dict(),
            )
            self._count("processed")
            self._count(result.decision.value.lower())
            self._log("INFO", f"{row.org_name}: qaror={result.decision.value}, "
                              f"topilmalar={len(result.findings)}", key)
            self._print_result(row, report, result)

            action, site_text = self._act(modal, result.decision, result.comment, key)
            record.update(action=action, site_check_text=site_text)
            acted = action in ("accepted", "rejected", "taken_manual")
        except Exception as exc:
            self._count("failed")
            record.update(action="failed", error=repr(exc))
            self._log("ERROR", f"Xatolik: {exc!r}", key)
            try:
                self._save_debug(page, key, page.content())
            except Exception:
                self._screenshot(page, key)
        finally:
            self.db.upsert_report(record)
            try:
                modal.close()
            except Exception:
                pass
        return acted

    def _act(self, modal: ReportModal, decision: Decision, comment: str, key: str) -> tuple[str, str]:
        """Qaror bo'yicha tugmalarni bosadi. (action, sayt_tekshiruv_matni) qaytaradi."""
        if not self.s.is_live:
            return "dry_run", ""

        wants = (
            (decision is Decision.ACCEPT and self.s.auto_accept)
            or (decision is Decision.REJECT and self.s.auto_reject)
            or (decision is Decision.MANUAL and self.s.manual_take and bool(comment))
        )
        if not wants:
            return "skipped", ""
        if self._limit_reached():
            return "skipped_limit", ""

        if modal.can_take():
            modal.take()
        elif not modal.is_editable():
            buttons = ", ".join(modal.visible_buttons()) or "-"
            self._log("WARNING", "«Olish» tugmasi ham, izoh maydoni ham topilmadi (hisobot boshqa "
                                 f"inspektorda bo'lishi mumkin). Ko'rinib turgan tugmalar: {buttons}", key)
            self._save_debug(page=modal.page, key=key, html=modal.page.content())
            return "not_editable", ""

        site_text = modal.run_site_check() if self.s.click_site_check else ""
        if decision is Decision.ACCEPT and site_check_warnings(site_text):
            # Saytning o'z tekshiruvi ogohlantirdi - qabul qilmaymiz, sayt yozgan matn qoralama bo'lib qoladi
            self._log("WARNING", "Sayt «Tekshirish» ogohlantirish berdi: "
                      + "; ".join(site_check_warnings(site_text)) + " — inspektorga qoldirildi", key)
            return "taken_manual", site_text

        modal.write_comment(comment)
        human_pause(self.s, 0.5)

        if decision is Decision.MANUAL:
            # Hisobot "Menga biriktirilgan" tabida izoh qoralamasi bilan inspektorni kutadi
            self._log("INFO", "Qo'lda ko'rish uchun olindi, izoh qoralamasi yozildi", key)
            return "taken_manual", site_text

        if self.s.confirm_each:
            answer = self._ask_confirmation(decision, comment, site_text)
            if answer != "ha":
                modal.release()  # "Bo'shatish" - hisobot YANGI ro'yxatiga qaytadi
                self._log("INFO", "Inspektor tasdiqlamadi - hisobot bo'shatildi", key)
                if answer == "q":
                    self.stop_requested = True
                return "declined", site_text

        if decision is Decision.ACCEPT:
            modal.accept()
            action = "accepted"
        else:
            modal.reject()
            action = "rejected"
        self.actions_done += 1
        self._log("INFO", f"Bajarildi: {action}", key)
        return action, site_text

    # ---------- natijani chiqarish ----------

    def _print_result(self, row: ListRow, report, result) -> None:
        """Har bir hisobot bo'yicha tahlil natijasini to'liq chiqaradi (terminal yoki oyna)."""
        labels = {"ACCEPT": "XATO YO'Q - qabul qilsa bo'ladi",
                  "REJECT": "XATO BOR - qaytarish kerak",
                  "MANUAL": "ROBOT HAL QILMADI - inspektor o'zi ko'rishi kerak"}
        lines = ["", "-" * 70,
                 f"{row.org_name}  |  STIR {row.inn}  |  OPF {row.opf}  |  {row.submitted_at}",
                 f"O'qilgan savollar: {len(report.items)} ta ({', '.join(report.items) or '-'})"]
        if result.findings:
            lines.append("Topilmalar:")
            for f in result.findings:
                code = f"{f.code}: " if f.code else ""
                lines.append(f"  [{f.severity.value}{', ichki' if f.internal else ''}] {code}{f.text}")
        else:
            lines.append("Topilmalar: yo'q")
        lines.append(f"ROBOT XULOSASI: {labels.get(result.decision.value, result.decision.value)}")
        if not self.s.is_live:
            lines.append("(SINOV REJIMI: saytda hech qanday tugma bosilmadi)")
        if result.comment:
            lines.append("Izoh matni:")
            lines += [f"  | {line}" for line in result.comment.splitlines()]
        lines.append("-" * 70)
        self.out("\n".join(lines))

    def _ask_confirmation(self, decision: Decision, comment: str, site_text: str) -> str:
        """'ha' - bajarish, 'yo'q' - bo'shatib o'tkazish, 'q' - bo'shatib robotni to'xtatish."""
        if self.confirm is not None:
            return self.confirm(decision, comment, site_text)
        if site_text:
            print("Sayt «Tekshirish» natijasi:")
            for line in site_text.splitlines():
                print(f"  | {line}")
        action = "QABUL QILINSINMI" if decision is Decision.ACCEPT else "QAYTARILSINMI"
        print("\a")  # ovozli signal - robot javob kutyapti
        print("#" * 70)
        print(f"#  ROBOT SIZNING JAVOBINGIZNI KUTYAPTI: hisobot {action}?")
        print("#  Brauzerdagi izohni tekshiring, keyin shu yerga yozing:")
        print("#    ha   - tugmani bosish      yo'q - bo'shatib o'tkazish      q - to'xtatish")
        print("#" * 70)
        while True:
            try:
                answer = input(f">>> Hisobot {action}? [ha / yo'q / q = to'xtatish]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return "q"
            if answer in ("ha", "h", "yes"):
                return "ha"
            if answer in ("yo'q", "yoq", "yo", "n", "no"):
                return "yo'q"
            if answer in ("q", "stop"):
                return "q"

    def _save_debug(self, page: Page, key: str, html: str) -> None:
        """Muammo bo'lgan paytdagi sahifa HTML'i va skrinshotini data/screens ga saqlaydi."""
        self._screenshot(page, key)
        self.s.screens_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() else "_" for c in key)
        path = self.s.screens_dir / f"{safe}.html"
        path.write_text(html, encoding="utf-8")
        self._log("INFO", f"Diagnostika saqlandi: {path}", key)

    def _screenshot(self, page: Page, key: str) -> None:
        try:
            self.s.screens_dir.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in key)
            page.screenshot(path=str(self.s.screens_dir / f"{safe}.png"), full_page=True)
        except Exception:
            pass

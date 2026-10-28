"""Hisobot oynasi (modal): ochish, matnini o'qish va tugmalarni bosish.

Oynadagi oqim (skrinshotlar bo'yicha):
  Yangi      -> [Olish]
  Jarayonda  -> izoh maydoni + [Tekshirish] [Qaytarish] [Qabul qilish] [Bo'shatish]
"""
from __future__ import annotations

import time

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PwTimeout

from ..config import Settings
from . import selectors as S
from .browser import human_pause


class ModalError(RuntimeError):
    pass


class ReportModal:
    def __init__(self, page: Page, settings: Settings):
        self.page = page
        self.settings = settings
        self.root: Locator | None = None

    # ---------- ochish / o'qish / yopish ----------

    def open_from_row(self, row: Locator) -> None:
        row.locator("a, button").filter(has_text=S.VIEW_BUTTON).first.click()
        self.root = self._wait_visible()

    def _wait_visible(self, timeout_s: float = 15) -> Locator:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for sel in S.MODAL_CANDIDATES:
                loc = self.page.locator(f"{sel} >> visible=true").first
                if loc.count():
                    return loc
            self.page.wait_for_timeout(300)
        raise ModalError("Hisobot oynasi ochilmadi")

    def read_text(self, settle_ms: int = 700, timeout_s: float = 20) -> str:
        """Matn o'zgarishdan to'xtaguncha kutadi (ma'lumot AJAX bilan yuklanishi mumkin)."""
        last, stable = "", 0
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            text = self.root.inner_text()
            if text == last and len(text) > 50:
                stable += 1
                if stable >= 2:
                    return text
            else:
                stable = 0
            last = text
            self.page.wait_for_timeout(settle_ms)
        return last

    def html(self) -> str:
        return self.root.inner_html()

    def close(self) -> None:
        if self.root is None:
            return
        self.page.keyboard.press("Escape")
        try:
            self.root.wait_for(state="hidden", timeout=3000)
        except PwTimeout:
            close_btn = self.page.locator(S.MODAL_CLOSE).first
            if close_btn.count():
                close_btn.click()
        self.root = None

    # ---------- holat ----------

    def _button(self, pattern) -> Locator:
        """Ko'rinib turgan tugma: avval oyna ichidan, topilmasa butun sahifadan (pastki panel oynadan tashqarida bo'lishi mumkin)."""
        loc = self.root.locator(S.CLICKABLE).filter(has_text=pattern).filter(visible=True)
        if not loc.count():
            loc = self.page.locator(S.CLICKABLE).filter(has_text=pattern).filter(visible=True)
        return loc.first

    def _textarea(self) -> Locator:
        loc = self.root.locator(S.COMMENT_TEXTAREA).filter(visible=True)
        if not loc.count():
            loc = self.page.locator(S.COMMENT_TEXTAREA).filter(visible=True)
        return loc.last

    def can_take(self) -> bool:
        return self._button(S.BTN_TAKE).count() > 0

    def is_editable(self) -> bool:
        """Hisobot bizda (Jarayonda) - izoh maydoni va Qabul tugmasi ko'rinadi."""
        return self._textarea().count() > 0 and self._button(S.BTN_ACCEPT).count() > 0

    def visible_buttons(self) -> list[str]:
        """Diagnostika uchun: sahifadagi ko'rinib turgan barcha tugmalar matni."""
        loc = self.page.locator(S.CLICKABLE).filter(visible=True)
        return [t.strip() for t in loc.all_inner_texts() if t.strip()][:60]

    # ---------- amallar ----------

    def take(self) -> None:
        """[Olish] - hisobotni o'zimizga biriktiramiz."""
        self._button(S.BTN_TAKE).click()
        deadline = time.monotonic() + self.settings.timeout_ms / 1000
        while time.monotonic() < deadline and not self.is_editable():
            self.page.wait_for_timeout(300)
        if not self.is_editable():
            raise ModalError("«Olish» bosildi, lekin izoh maydoni va «Qabul qilish» tugmasi chiqmadi")
        human_pause(self.settings, 0.5)

    def run_site_check(self) -> str:
        """Saytning o'z [Tekshirish] tugmasini bosib, izoh maydoniga chiqqan matnni qaytaradi."""
        textarea = self._textarea()
        before = textarea.input_value()
        self._button(S.BTN_SITE_CHECK).click()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and textarea.input_value() == before:
            self.page.wait_for_timeout(300)
        return textarea.input_value()

    def write_comment(self, text: str) -> None:
        textarea = self._textarea()
        textarea.click()
        textarea.fill(text)
        if textarea.input_value().strip() != text.strip():
            raise ModalError("Izoh maydoniga matn to'liq yozilmadi")
        human_pause(self.settings, 0.5)

    def accept(self) -> None:
        self._submit(S.BTN_ACCEPT)

    def reject(self) -> None:
        self._submit(S.BTN_REJECT)

    def release(self) -> None:
        self._button(S.BTN_RELEASE).click()

    def _submit(self, pattern) -> None:
        self._button(pattern).click()
        self.page.wait_for_timeout(500)
        self._screenshot("submit")  # amaldan keyingi holat (tasdiq oynasi chiqqan bo'lishi mumkin)
        self._confirm_if_asked()
        if not self._wait_done():
            self._screenshot("submit_timeout")
            raise ModalError("Amal bajarilganini tasdiqlab bo'lmadi (oyna yopilmadi / holat o'zgarmadi)")

    def _screenshot(self, suffix: str) -> None:
        """Live rejimda amaldan keyingi holatni data/screens ga saqlaydi (diagnostika)."""
        if not self.settings.is_live:
            return
        try:
            self.settings.screens_dir.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(self.settings.screens_dir / f"last_{suffix}.png"))
        except Exception:
            pass

    def _confirm_if_asked(self, timeout_s: float = 3) -> None:
        """SweetAlert/Bootstrap tasdiqlash oynasi chiqsa, "Ha/OK" ni bosadi."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            btn = self.page.get_by_role("button", name=S.CONFIRM_BUTTONS)
            for k in range(btn.count()):
                if btn.nth(k).is_visible():
                    btn.nth(k).click()
                    return
            self.page.wait_for_timeout(250)

    def _wait_done(self, timeout_s: float = 15) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if not self.root.is_visible():
                return True
            if S.DONE_TEXT.search(self.root.inner_text()[-400:]):
                return True
            self.page.wait_for_timeout(400)
        return False

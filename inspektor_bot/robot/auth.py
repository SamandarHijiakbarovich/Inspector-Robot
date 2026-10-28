"""Tizimga kirish va tashkilotni tanlash.

Saytga OneID (id.egov.uz) yoki ERI orqali kiriladi. Robot login/parolni o'zi kiritmaydi:
sessiya bo'lmasa, brauzer oynasida siz o'zingiz kirasiz, robot esa shu oynada kutib turadi
va kirganingizdan keyin ishni davom ettiradi. Sessiya data/browser_profile da saqlanadi.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PwTimeout

from ..config import Settings
from .browser import open_browser


log = logging.getLogger(__name__)


class LoginRequired(RuntimeError):
    pass


def _path(page: Page) -> str:
    # Faqat yo'lni tekshiramiz: login manzilida ham "?next=/uz/inspector/..." bo'ladi
    return urlparse(page.url).path


def on_organizations(page: Page) -> bool:
    return "/organizations" in _path(page)


def is_logged_in(page: Page) -> bool:
    url = urlparse(page.url)
    return (
        url.netloc.endswith("inspektor.stat.uz")
        and "/inspector/" in url.path
        and "/login" not in url.path
    )


def select_organization(page: Page, settings: Settings) -> None:
    """"Tashkilotni o'zgartirish" sahifasida kerakli tashkilotni bosadi (?organization_id=... havolasi)."""
    if settings.org_inn:
        row = page.locator("tr", has_text=settings.org_inn).first
    else:
        row = page.locator("table tbody tr").first
    if not row.count():
        raise LoginRequired(f"Tashkilotlar ro'yxatida STIR {settings.org_inn} topilmadi (.env dagi ORG_INN ni tekshiring)")
    row.locator("a").first.click()
    try:
        page.wait_for_url(lambda url: "/organizations" not in urlparse(url).path, timeout=10000)
    except PwTimeout:
        page.wait_for_load_state("networkidle")


def wait_for_manual_login(page: Page, settings: Settings, wait_minutes: int = 10) -> None:
    """Foydalanuvchi ochiq oynada o'zi kirishini kutadi (OneID / ERI)."""
    log.warning("Tizimga kirilmagan. Ochilgan brauzer oynasida OneID yoki ERI orqali o'zingiz kiring. "
                "Robot %s daqiqagacha kutadi, oynani yopmang.", wait_minutes)
    deadline = time.monotonic() + wait_minutes * 60
    while time.monotonic() < deadline:
        if on_organizations(page):
            select_organization(page, settings)
        if is_logged_in(page):
            log.info("Kirish muvaffaqiyatli: %s", page.url)
            return
        page.wait_for_timeout(1500)
    raise LoginRequired("Belgilangan vaqt ichida tizimga kirilmadi.")


def goto(page: Page, settings: Settings, url: str) -> None:
    """Sahifaga o'tadi. Login yoki tashkilot tanlash so'ralsa - hal qilib, qayta o'tadi.

    Sayt tanlangan tashkilotni sessiyada saqlaydi va u yo'qolsa istalgan sahifadan
    /organizations/ ga qaytaradi, shuning uchun har bir o'tishda tekshiramiz.
    """
    page.goto(url, wait_until="networkidle")
    if not is_logged_in(page) and not on_organizations(page):
        if settings.headless:
            raise LoginRequired(
                "Tizimga kirilmagan yoki sessiya eskirgan. Avval «Kirish» tugmasini bosib, OneID orqali kiring."
            )
        wait_for_manual_login(page, settings)
        page.goto(url, wait_until="networkidle")
    if on_organizations(page):
        select_organization(page, settings)
        page.goto(url, wait_until="networkidle")
    if on_organizations(page):
        raise LoginRequired("Tashkilotni tanlab bo'lmadi - sayt yana tashkilot tanlash sahifasiga qaytardi")
    if not is_logged_in(page):
        raise LoginRequired(f"Kerakli sahifa ochilmadi (sahifa: {page.url})")


def ensure_session(page: Page, settings: Settings) -> None:
    goto(page, settings, settings.home_url)


def interactive_login(settings: Settings, wait_minutes: int = 10) -> None:
    """Brauzerni ochadi va foydalanuvchi o'zi kirishini kutadi."""
    with open_browser(settings, headless=False) as page:
        page.goto(settings.home_url, wait_until="domcontentloaded")
        if on_organizations(page):
            select_organization(page, settings)
        if is_logged_in(page):
            log.info("Siz allaqachon tizimga kirgansiz, qayta kirish shart emas.")
            return
        wait_for_manual_login(page, settings, wait_minutes)
        log.info("Sessiya saqlandi. Endi «Ishga tushirish» tugmasini bosishingiz mumkin.")

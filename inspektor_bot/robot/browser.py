"""Brauzerni ishga tushirish. Doimiy profil ishlatiladi - bir marta kirsangiz sessiya saqlanadi."""
from __future__ import annotations

import random
import time
from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Page, sync_playwright

from ..config import Settings


@contextmanager
def open_browser(settings: Settings, headless: bool | None = None) -> Iterator[Page]:
    settings.profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        kwargs = dict(
            user_data_dir=str(settings.profile_dir),
            headless=settings.headless if headless is None else headless,
            viewport={"width": 1600, "height": 1000},
            locale="uz-UZ",
            # Playwright standart holatda --no-sandbox qo'shadi; oddiy brauzerdek ishlashi uchun o'chiramiz
            chromium_sandbox=True,
        )
        if settings.browser_channel and settings.browser_channel != "chromium":
            kwargs["channel"] = settings.browser_channel
        context = p.chromium.launch_persistent_context(**kwargs)
        context.set_default_timeout(settings.timeout_ms)
        page = context.pages[0] if context.pages else context.new_page()
        # JS confirm()/alert() oynalarini avtomatik tasdiqlash
        page.on("dialog", lambda dialog: dialog.accept())
        try:
            yield page
        finally:
            context.close()


def human_pause(settings: Settings, factor: float = 1.0) -> None:
    """Inson tezligiga yaqin tasodifiy pauza (saytga ortiqcha yuk bermaslik uchun ham)."""
    time.sleep(random.uniform(settings.delay_min, settings.delay_max) * factor)

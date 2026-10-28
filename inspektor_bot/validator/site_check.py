"""Saytning o'z "Tekshirish" tugmasi izoh maydoniga yozgan matnni tahlil qilish.

Sayt avtomatik tekshiruvi (autocheck) xarajatlar ro'yxatini va "⚠ ..." ogohlantirishlarini
yozadi. Robot o'z qoidalari "qabul" desa ham, sayt ogohlantirsa - hisobot inspektorga qoldiriladi.
"""
from __future__ import annotations

from ..parsing.normalize import normalize

WARNING_MARKERS = ("⚠", "aniqlik kiriting", "ko'rsatilmagan", "mos kelmaydi", "xato", "noto'g'ri",
                   "tekshiring")


def site_check_warnings(text: str) -> list[str]:
    """Ogohlantirish bo'lgan qatorlarni qaytaradi (bo'sh ro'yxat - ogohlantirish yo'q)."""
    found = []
    for raw in (text or "").splitlines():
        line = normalize(raw)
        low = line.lower()
        if low.startswith("izoh:"):
            continue  # respondentning o'z izohi
        if any(m in low for m in WARNING_MARKERS):
            found.append(line.lstrip("⚠ ").strip())
    return found

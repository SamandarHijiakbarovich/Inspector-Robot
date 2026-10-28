"""Saytdagi elementlarni topish uchun barcha selektorlar BIR joyda.

Sayt dizayni o'zgarsa, faqat shu faylni tahrirlang. Matnli tugmalar regex orqali
qidiriladi, chunki o'zbekcha tutuq belgisi har xil yozilishi mumkin (Ko'rish / Koʻrish).
"""
from __future__ import annotations

import re

# ʻ ʼ ‘ ’ ' ` - Unicode kodlari bilan yozilgan: regex ichida haqiqiy ' yoki ` belgisi bo'lsa,
# Playwright uni brauzerga uzatishda selektorni buzadi ("Invalid flags supplied to RegExp")
_APOS = r"[ʻʼ‘’\x27\x60]?"


def uz_re(text: str, flags: int = re.I) -> re.Pattern:
    """uz_re("Ko'rish") -> Koʻrish, Ko'rish, Ko‘rish ... hammasiga mos regex."""
    return re.compile(text.replace("'", _APOS), flags)


# --- Login / tashkilot tanlash (login sahifasi skrinshotda yo'q - TEKSHIRISH KERAK) ---
LOGIN_USERNAME = "input[name='username'], input[name='login'], input[type='email'], input[type='text']"
LOGIN_PASSWORD = "input[type='password']"
LOGIN_SUBMIT = "button[type='submit'], input[type='submit']"

# --- Hisobotlar ro'yxati ("Biznesni ro'yxatga olish" moduli, #ci-root) ---
# Tablar: <a class="ci-tab" data-tab="pending">Yangi <span class="ci-tab__n">90</span></a>
TABS = {
    "new": "a.ci-tab[data-tab='pending']",
    "mine": "a.ci-tab[data-tab='my']",
    "accepted": "a.ci-tab[data-tab='accepted']",
    "rejected": "a.ci-tab[data-tab='rejected']",
    "all": "a.ci-tab[data-tab='all']",
}
# Ro'yxat JavaScript bilan to'ldiriladi; avval <td class="ci-empty">Yuklanmoqda…</td> turadi
LIST_TABLE = "#ci-root .ci-list table.ci-table"
LIST_PLACEHOLDER = "#ci-root .ci-list tbody.ci-body td.ci-empty"
LIST_PAGER = "#ci-root .ci-pager"
VIEW_BUTTON = uz_re(r"ko'rish")
# Sahifalash tugmalari hali ko'rilmagan (90 ta hisobot bitta sahifada bo'lishi mumkin) - TEKSHIRISH KERAK
NEXT_PAGE = (
    ".ci-pager a:text-matches('^\\s*(›|»|>|Keyingi)\\s*$'):not(.disabled):not([disabled]), "
    ".ci-pager button:text-matches('^\\s*(›|»|>|Keyingi)\\s*$'):not(.disabled):not([disabled]), "
    ".pagination li:not(.disabled) a[rel='next']"
)

# --- Hisobot oynasi (modal) ---
MODAL_CANDIDATES = (
    ".modal.show .modal-content",
    ".modal.show",
    "[role='dialog']",
)
MODAL_CLOSE = ".modal.show .close, .modal.show .btn-close, .modal.show [data-dismiss='modal'], .modal.show [data-bs-dismiss='modal']"
COMMENT_TEXTAREA = "textarea"

# Tugmalar ichida ikonka bo'lishi mumkin ("🔗 Olish", "✔ Qabul qilish") - \W* shuni o'tkazib yuboradi
CLICKABLE = "button, a, [role='button'], input[type='button'], input[type='submit']"
BTN_TAKE = uz_re(r"^\W*olish\W*$")
BTN_SITE_CHECK = uz_re(r"^\W*tekshirish\W*$")
BTN_ACCEPT = uz_re(r"^\W*qabul\s+qilish\W*$")
BTN_REJECT = uz_re(r"^\W*qaytarish\W*$")
BTN_RELEASE = uz_re(r"^\W*bo'shatish\W*$")

# Qabul/Qaytarishdan keyin chiqishi mumkin bo'lgan tasdiqlash oynasi tugmalari
CONFIRM_BUTTONS = uz_re(r"^\s*(ha|ok|tasdiqlash|yes|да)\s*$")

# Amal muvaffaqiyatli bajarilganini bildiruvchi matnlar
DONE_TEXT = uz_re(r"qabul qilingan|qaytarilgan|muvaffaqiyatli")

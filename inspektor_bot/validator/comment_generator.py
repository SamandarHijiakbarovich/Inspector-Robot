"""Tekshiruv natijasidan korxonaga yuboriladigan izoh matnini yasaydi.

Har bir qoida (rule_id) uchun bitta shablon. Shablon - oddiy str.format satri
yoki params'dan matn qaytaruvchi funksiya. Matnni o'zgartirish uchun faqat
shu yerdagi TEMPLATES ni tahrirlash kifoya - qoidalar kodiga tegish shart emas.
"""
from __future__ import annotations

from typing import Callable

from .models import Decision, Finding, Severity

DEFAULT_ACCEPT_TEXT = "Tizim tomonidan avtomatik tekshirildi va qabul qilindi."
REJECT_HEADER = "Hisobotda quyidagi nomuvofiqliklar aniqlandi:"
MANUAL_HEADER = "Hisobotda quyidagi holatlarga aniqlik kiritish talab etiladi:"
FOOTER = "Iltimos, ma'lumotlarni qayta tekshirib, hisobotni qayta topshiring."


def _site_warning(p: dict) -> str:
    text = p["warning"]
    if p.get("izoh"):
        text += f" Respondent izohi: «{p['izoh']}»."
    return text


TEMPLATES: dict[str, str | Callable[[dict], str]] = {
    "REQUIRED_EMPTY": "{code}-savol to'ldirilmagan: «{question}».",
    "NEGATIVE_VALUE": "{code}-savolda manfiy qiymat kiritilgan ({amount} {unit}).",
    "CHILDREN_SUM_MISMATCH": (
        "{code}-satrdagi yakuniy summa ({parent} {unit}) {first}–{last} satrlar "
        "yig'indisiga ({children_sum} {unit}) mos kelmadi, farq {diff} {unit}."
    ),
    "TOTAL_MISMATCH": (
        "{code}-savoldagi «Jami» ({total} {unit}) tarkibiy qismlar yig'indisiga "
        "({parts_sum} {unit}) teng emas, farq {diff} {unit}."
    ),
    "STOCK_INCOMPLETE": "{code}-savolda yil boshi va yil oxiri qiymatlari to'liq ko'rsatilmagan.",
    "NO_EXPENSES": "Jami aylanma (3.1) {revenue} mln so'm ko'rsatilgan, ammo xarajatlar ko'rsatilmagan.",
    "NO_REVENUE": "Xarajatlar {expenses} mln so'm ko'rsatilgan, ammo jami aylanma (3.1) 0 ga teng.",
    "EXPENSE_RATIO": (
        "Xarajatlar ({expenses} mln so'm) jami aylanmadan ({revenue} mln so'm) "
        "{ratio} baravar ko'p."
    ),
    "FARM_NO_AGRI": (
        "Fermer/dehqon xo'jaligi uchun qishloq xo'jaligi daromadi (3.1a) 0 ga teng, "
        "jami aylanma esa {revenue} mln so'm."
    ),
    "EXPENSE_TOTAL_MISMATCH": (
        "2.1-savoldagi jami xarajatlar ({total} mln so'm) 2.2-savoldagi xarajatlar ro'yxati "
        "jamisiga ({jami} mln so'm) mos kelmadi, farq {diff} mln so'm."
    ),
    "ZERO_ACTIVITY": (
        "2025 yil uchun jami aylanma (3.1) va jami xarajatlar (2.1) 0 ga teng — "
        "korxona faoliyati bo'yicha ma'lumotlar ko'rsatilmagan."
    ),
    "PHONE_MISSING": "Telefon raqami ko'rsatilmagan.",
    "PHONE_INVALID": "Telefon raqami noto'g'ri formatda: {phone}.",
    "SITE_WARNING": _site_warning,
    # internal=True - faqat inspektor/log uchun, korxonaga yuborilmaydi
    "ITEM_NOT_FOUND": "{code}-savol hisobot matnidan topilmadi (forma o'zgargan yoki parser moslashtirilishi kerak).",
    "PARSE_EMPTY": "Hisobot matnidan birorta savol ajratib olinmadi.",
    "RULE_CRASH": "«{rule}» qoidasi bajarilmadi: {error}",
}


def render_finding(f: Finding) -> str:
    template = TEMPLATES.get(f.rule_id)
    params = {"code": f.code or "", **f.params}
    try:
        if callable(template):
            return template(params)
        if template:
            return template.format(**params)
    except (KeyError, IndexError, ValueError):
        pass
    return f"{f.rule_id} ({f.code or '-'}): {f.params}"


def decide(findings: list[Finding]) -> Decision:
    """ERROR -> qaytarish; WARNING yoki robotning ichki muammosi -> qo'lda; aks holda qabul."""
    if any(f.internal for f in findings):
        return Decision.MANUAL  # o'zimiz to'liq o'qiy olmagan hisobotni hech qachon avtomatik hal qilmaymiz
    if any(f.severity is Severity.ERROR for f in findings):
        return Decision.REJECT
    if any(f.severity is Severity.WARNING for f in findings):
        return Decision.MANUAL
    return Decision.ACCEPT


def _short(text: str, limit: int = 160) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def finding_block(n: int, f: Finding) -> str:
    """Saytning "Tekshirish" matniga o'xshash blok:

    4.4. Tayyor mahsulot qoldig'i qiymati (...)
       • 2025 yil boshiga: 3.3
       • 2025 yil oxiriga: 0
       ⚠ Tayyor mahsulot qoldig'i bir davrda 0, ... Respondent izohi: «...».
    """
    text = f.text or render_finding(f)
    question = f.params.get("_question")
    if not (f.code and question):
        return f"{n}. {text}"
    lines = [f"{n}. {f.code}. {_short(question)}"]
    lines += [f"   • {v}" for v in f.params.get("_values", [])]
    lines.append(f"   ⚠ {text}")
    return "\n".join(lines)


def _fit(header: str, findings: list[Finding], footer: str, max_len: int) -> str:
    """Izoh saytdagi maydon sig'imidan oshib ketmasligi uchun ro'yxatni qisqartiradi."""
    parts = [header]
    for n, f in enumerate(findings, 1):
        block = finding_block(n, f)
        rest = len(findings) - n
        tail = f"... va yana {rest} ta nomuvofiqlik." if rest else ""
        projected = len("\n".join(parts + [block, tail, footer]))
        if projected > max_len and n > 1:
            parts.append(f"... va yana {len(findings) - n + 1} ta nomuvofiqlik.")
            break
        parts.append(block)
    parts.append(footer)
    return "\n".join(parts)[:max_len]


def build_comment(
    decision: Decision,
    findings: list[Finding],
    *,
    accept_text: str = DEFAULT_ACCEPT_TEXT,
    max_len: int = 2000,
) -> str:
    if decision is Decision.ACCEPT:
        return accept_text

    public = [f for f in findings if not f.internal]
    errors = [f for f in public if f.severity is Severity.ERROR]
    if decision is Decision.REJECT:
        return _fit(REJECT_HEADER, errors, FOOTER, max_len)

    # MANUAL - inspektor uchun tayyor qoralama (u xohlasa shu matn bilan qaytaradi)
    warnings = [f for f in public if f.severity is Severity.WARNING]
    if not errors and not warnings:
        return ""
    return _fit(MANUAL_HEADER, errors + warnings, FOOTER, max_len)

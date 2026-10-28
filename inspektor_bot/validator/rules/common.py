"""Barcha shakllar uchun umumiy (matematik) qoidalar.

Har bir qoida: (report, ctx) -> Finding'lar ro'yxati.
Finding faqat rule_id va params saqlaydi; korxonaga yoziladigan matnni
comment_generator.TEMPLATES dagi shablon yasaydi.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from ..models import Finding, Report, Severity
from ...parsing.normalize import format_amount


@dataclass
class RuleContext:
    tolerance: float = 0.1
    # Saytning sariq ogohlantirishlari: WARNING - inspektorga qoldirish, ERROR - qaytarish
    site_warning_severity: Severity = Severity.WARNING


Rule = Callable[[Report, RuleContext], Iterable[Finding]]

SITE_WARNING_MARKERS = ("ko'rsatilmagan", "aniqlik kiriting", "mos kelmaydi", "to'ldirilmagan",
                        "tekshiring")
IZOH_RE = re.compile(r"^izoh\s*:\s*(.*)$", re.I)


def _tol(ctx: RuleContext, n_parts: int) -> float:
    # Har bir qiymat 0.1 gacha yaxlitlangani uchun ko'p qismli yig'indida xato to'planadi
    return max(ctx.tolerance, 0.05 * n_parts)


def _short(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def required(codes: Iterable[str]) -> Rule:
    """Savollar mavjud va javob berilganligini tekshiradi."""
    codes = tuple(codes)

    def check(report: Report, ctx: RuleContext):
        for code in codes:
            item = report.item(code)
            if item is None:
                # Kod umuman topilmasa - bu ko'pincha parser/forma o'zgarishi, korxona aybi emas
                yield Finding("ITEM_NOT_FOUND", Severity.WARNING, code, internal=True)
            elif not item.has_answer:
                yield Finding("REQUIRED_EMPTY", Severity.ERROR, code,
                              {"question": _short(item.question)})

    check.__name__ = "required"
    return check


def non_negative(report: Report, ctx: RuleContext):
    for code, item in report.items.items():
        for v in item.values:
            if v.amount < 0:
                yield Finding("NEGATIVE_VALUE", Severity.ERROR, item.code,
                              {"amount": format_amount(v.amount), "unit": v.unit or item.unit})


def children_sum(report: Report, ctx: RuleContext):
    """3.1 = 3.1a + 3.1b + ... ko'rinishidagi ota-bola satrlar yig'indisi."""
    for code, parent in report.items.items():
        if not re.fullmatch(r"\d{1,2}\.\d{1,2}", code):
            continue
        children = [it for c, it in report.items.items() if re.fullmatch(re.escape(code) + r"[a-z]", c)]
        if not children:
            continue
        parent_total = parent.total()
        amounts = [c.total() for c in children]
        if parent_total is None or any(a is None for a in amounts):
            continue
        children_total = sum(amounts)
        diff = parent_total - children_total
        if abs(diff) > _tol(ctx, len(children)):
            yield Finding("CHILDREN_SUM_MISMATCH", Severity.ERROR, code, {
                "parent": format_amount(parent_total),
                "children_sum": format_amount(children_total),
                "diff": format_amount(abs(diff)),
                "first": children[0].code,
                "last": children[-1].code,
                "unit": parent.unit,
            })


def jami_sum(report: Report, ctx: RuleContext):
    """Savol ichidagi ro'yxat: tarkibiy qismlar yig'indisi "Jami" ga teng bo'lishi kerak."""
    for code, item in report.items.items():
        total = next((v for v in item.values if v.label and v.label.lower().startswith("jami")), None)
        parts = [v for v in item.values if v is not total and v.label and not v.is_period]
        if total is None or not parts:
            continue
        parts_sum = sum(v.amount for v in parts)
        diff = total.amount - parts_sum
        if abs(diff) > _tol(ctx, len(parts)):
            unit = total.unit or item.unit
            yield Finding("TOTAL_MISMATCH", Severity.ERROR, item.code, {
                "total": format_amount(total.amount),
                "parts_sum": format_amount(parts_sum),
                "diff": format_amount(abs(diff)),
                "unit": unit,
            })


def site_warnings(report: Report, ctx: RuleContext):
    """Saytning o'zi chiqargan ogohlantirishlar (sariq blok) - inspektor ko'rishi kerak."""
    for code, item in report.items.items():
        texts = item.texts
        izoh = next((IZOH_RE.match(t)[1] for t in texts if IZOH_RE.match(t)), "")
        for i, t in enumerate(texts):
            if IZOH_RE.match(t):
                continue
            # Sariq blok: ogohlantirish matni, uning ostida respondentning "Izoh: ..." javobi
            before_izoh = i + 1 < len(texts) and IZOH_RE.match(texts[i + 1])
            if before_izoh or any(m in t.lower() for m in SITE_WARNING_MARKERS):
                yield Finding("SITE_WARNING", ctx.site_warning_severity, item.code,
                              {"warning": t, "izoh": izoh})


def phone(report: Report, ctx: RuleContext):
    if not report.phone:
        yield Finding("PHONE_MISSING", Severity.WARNING)
        return
    digits = re.sub(r"\D", "", report.phone)
    if not (len(digits) == 12 and digits.startswith("998")) and len(digits) != 9:
        yield Finding("PHONE_INVALID", Severity.WARNING, params={"phone": report.phone})


DEFAULT_RULES: list[Rule] = [non_negative, children_sum, jami_sum, site_warnings]

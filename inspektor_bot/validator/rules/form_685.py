"""form_type=685 - "Biznesni ro'yxatga olish" (2-shakl) uchun qoidalar.

Savol kodlari skrinshotlardagi hisobot oynasidan olingan. Agar forma o'zgarsa,
REQUIRED_CODES va quyidagi mantiqiy qoidalarni yangilang.
"""
from __future__ import annotations

from ..models import Finding, Report, Severity
from ...parsing.normalize import format_amount
from . import common
from .common import RuleContext

REQUIRED_CODES = ("2.1", "2.3", "3.1", "4.1", "4.2", "4.3", "4.4")
# Forma bu satrlarni faqat 3.1 > 0 bo'lganda ko'rsatadi
REVENUE_BREAKDOWN = ("3.1a", "3.1b", "3.1c", "3.1d", "3.1e")
STOCK_CODES = ("4.1", "4.2", "4.3", "4.4")
EXPENSE_RATIO_LIMIT = 5.0  # xarajat aylanmadan necha baravar ko'p bo'lsa shubhali


def total_expenses(report: Report) -> float | None:
    """Jami xarajatlar: 2.1-savol (0 dan katta bo'lsa ichida ro'yxat va "Jami" chiqadi)."""
    if report.item("2.1") is not None:
        return report.amount("2.1")
    for item in report.items.values():
        if item.section and "xarajat" in item.section.lower():
            for v in item.values:
                if v.label and v.label.lower().startswith("jami"):
                    return v.amount
    return None


def stock_pairs(report: Report, ctx: RuleContext):
    for code in STOCK_CODES:
        item = report.item(code)
        if item is None or not item.has_answer:
            continue  # buni required() qoidasi aytadi
        if item.period("boshiga") is None or item.period("oxiriga") is None:
            yield Finding("STOCK_INCOMPLETE", Severity.ERROR, code)


def revenue_breakdown(report: Report, ctx: RuleContext):
    """3.1 > 0 bo'lsa, 3.1a–3.1e satrlari ko'rinishi va to'ldirilgan bo'lishi kerak."""
    revenue = report.amount("3.1")
    if not revenue or revenue <= 0:
        return
    for code in REVENUE_BREAKDOWN:
        item = report.item(code)
        if item is None:
            yield Finding("ITEM_NOT_FOUND", Severity.WARNING, code, internal=True)
        elif not item.has_answer:
            yield Finding("REQUIRED_EMPTY", Severity.ERROR, code, {"question": item.question[:80]})


def expense_total_matches_breakdown(report: Report, ctx: RuleContext):
    """2.1 (jami xarajatlar) = 2.2 dagi xarajatlar ro'yxatining "Jami" qatori."""
    total = report.item("2.1")
    breakdown = report.item("2.2")
    if total is None or breakdown is None or len(total.values) != 1:
        return
    jami = next((v.amount for v in breakdown.values if v.label and v.label.lower().startswith("jami")), None)
    if jami is None:
        return
    diff = total.values[0].amount - jami
    if abs(diff) > ctx.tolerance + 1e-9:  # 1e-9 - kasr sonlardagi yaxlitlash xatosi uchun
        yield Finding("EXPENSE_TOTAL_MISMATCH", Severity.ERROR, "2.1", {
            "total": format_amount(total.values[0].amount),
            "jami": format_amount(jami),
            "diff": format_amount(abs(diff)),
        })


def zero_activity(report: Report, ctx: RuleContext):
    """Aylanma ham, xarajat ham 0 - korxona butun yil hech qanday faoliyat ko'rsatmagan."""
    revenue = report.amount("3.1")
    expenses = total_expenses(report)
    if revenue == 0 and expenses == 0:
        yield Finding("ZERO_ACTIVITY", Severity.WARNING, "3.1")


def revenue_vs_expenses(report: Report, ctx: RuleContext):
    revenue = report.amount("3.1")
    expenses = total_expenses(report)
    if revenue is None or (revenue == 0 and expenses == 0):
        return  # ikkalasi 0 - buni zero_activity aytadi
    if revenue > 0 and not expenses:
        yield Finding("NO_EXPENSES", Severity.WARNING, "3.1", {"revenue": format_amount(revenue)})
    elif expenses and expenses > 0 and revenue == 0:
        yield Finding("NO_REVENUE", Severity.WARNING, "3.1", {"expenses": format_amount(expenses)})
    elif expenses and revenue > 0 and expenses > revenue * EXPENSE_RATIO_LIMIT:
        yield Finding("EXPENSE_RATIO", Severity.WARNING, "3.1", {
            "expenses": format_amount(expenses),
            "revenue": format_amount(revenue),
            "ratio": format_amount(expenses / revenue),
        })


def farm_agriculture(report: Report, ctx: RuleContext):
    """Fermer/dehqon xo'jaligi (OPF 130) daromadi asosan qishloq xo'jaligidan bo'lishi kutiladi."""
    if not report.meta.opf.strip().startswith("130"):
        return
    revenue = report.amount("3.1")
    agri = report.amount("3.1a")
    if revenue and revenue > 0 and (agri or 0) == 0:
        yield Finding("FARM_NO_AGRI", Severity.WARNING, "3.1a", {"revenue": format_amount(revenue)})


RULES = [
    common.required(REQUIRED_CODES),
    common.non_negative,
    common.children_sum,
    common.jami_sum,
    common.site_warnings,
    common.phone,
    stock_pairs,
    expense_total_matches_breakdown,
    revenue_breakdown,
    zero_activity,
    revenue_vs_expenses,
    farm_agriculture,
]

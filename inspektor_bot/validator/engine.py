"""Validator: hisobotga qoidalarni qo'llaydi, qaror chiqaradi va izoh yasaydi."""
from __future__ import annotations

from ..parsing.normalize import format_amount
from .comment_generator import DEFAULT_ACCEPT_TEXT, build_comment, decide, render_finding
from .models import Finding, Report, Severity, Value, ValidationResult
from .rules import RuleContext, get_rules

MAX_VALUES_IN_COMMENT = 8


def _format_value(v: Value) -> str:
    amount = f"{format_amount(v.amount)} {v.unit or ''}".strip()
    return f"{v.label}: {amount}" if v.label else amount


def _attach_context(report: Report, findings: list[Finding]) -> None:
    """Izohda savol matni va korxona kiritgan qiymatlar ko'rinishi uchun ularni topilmaga biriktiradi."""
    for f in findings:
        item = report.item(f.code) if f.code else None
        if item is None or f.internal:
            continue
        f.params.setdefault("_question", item.question)
        f.params.setdefault("_values", [_format_value(v) for v in item.values][:MAX_VALUES_IN_COMMENT])


def validate(
    report: Report,
    *,
    tolerance: float = 0.1,
    accept_text: str = DEFAULT_ACCEPT_TEXT,
    max_len: int = 2000,
    site_warning_action: str = "manual",
) -> ValidationResult:
    ctx = RuleContext(
        tolerance=tolerance,
        site_warning_severity=Severity.ERROR if site_warning_action == "reject" else Severity.WARNING,
    )
    findings: list[Finding] = []

    if not report.items:
        findings.append(Finding("PARSE_EMPTY", Severity.WARNING, internal=True))
    else:
        for rule in get_rules(report.meta.form_type):
            try:
                findings.extend(rule(report, ctx))
            except Exception as exc:  # bitta qoidadagi xato butun tekshiruvni to'xtatmasin
                findings.append(Finding(
                    "RULE_CRASH", Severity.WARNING, internal=True,
                    params={"rule": getattr(rule, "__name__", str(rule)), "error": repr(exc)},
                ))

    _attach_context(report, findings)
    for f in findings:
        f.text = render_finding(f)

    decision = decide(findings)
    comment = build_comment(decision, findings, accept_text=accept_text, max_len=max_len)
    return ValidationResult(decision=decision, findings=findings, comment=comment)

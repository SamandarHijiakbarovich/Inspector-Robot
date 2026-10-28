"""Hisobot shakli (form_type) bo'yicha qoidalar to'plami.

Yangi shakl qo'shish: rules/form_XXX.py yarating, RULES ro'yxatini yozing
va quyidagi RULESETS lug'atiga qo'shing.
"""
from __future__ import annotations

from . import common, form_685
from .common import Rule, RuleContext

RULESETS: dict[str, list[Rule]] = {
    "685": form_685.RULES,
}


def get_rules(form_type: str) -> list[Rule]:
    return RULESETS.get(str(form_type), common.DEFAULT_RULES)


__all__ = ["get_rules", "Rule", "RuleContext", "RULESETS"]

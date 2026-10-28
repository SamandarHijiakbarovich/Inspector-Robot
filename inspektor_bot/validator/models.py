"""Hisobot va tekshiruv natijalari uchun ma'lumot modellari."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum

PERIOD_RE = re.compile(r"(boshiga|oxiriga|holatiga)\b", re.I)


class Severity(str, Enum):
    ERROR = "ERROR"      # aniq xato -> hisobot qaytariladi
    WARNING = "WARNING"  # shubhali holat -> inspektor qo'lda ko'radi
    INFO = "INFO"        # faqat ma'lumot uchun


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MANUAL = "MANUAL"


@dataclass
class Value:
    amount: float
    unit: str | None = None
    label: str | None = None

    @property
    def is_period(self) -> bool:
        return bool(self.label and PERIOD_RE.search(self.label))


@dataclass
class Item:
    """Bitta savol: kodi (masalan "3.1a"), savol matni va javoblari."""
    code: str
    question: str
    section: str | None = None
    values: list[Value] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)

    @property
    def has_answer(self) -> bool:
        return bool(self.values or self.texts)

    def total(self) -> float | None:
        """"Jami" qatori bo'lsa o'shani, bitta qiymat bo'lsa o'shani qaytaradi."""
        for v in self.values:
            if v.label and v.label.lower().startswith("jami"):
                return v.amount
        if len(self.values) == 1:
            return self.values[0].amount
        return None

    def period(self, word: str) -> float | None:
        """period("boshiga") / period("oxiriga") - yil boshi/oxiri qiymati."""
        for v in self.values:
            if v.label and word in v.label.lower():
                return v.amount
        return None

    @property
    def unit(self) -> str:
        for v in self.values:
            if v.unit:
                return v.unit
        return "mln so'm"


@dataclass
class Section:
    number: int
    title: str


@dataclass
class ReportMeta:
    """Ro'yxat jadvalidan va oyna pastki qismidan olinadigan ma'lumotlar."""
    form_type: str = ""
    form_label: str = ""
    inn: str = ""
    org_name: str = ""
    opf: str = ""
    soato: str = ""
    submitted_at: str = ""
    status: str = ""
    assigned_inspector: str = ""

    @property
    def key(self) -> str:
        return f"{self.form_type}:{self.inn}:{self.submitted_at}"


@dataclass
class Report:
    meta: ReportMeta = field(default_factory=ReportMeta)
    sections: list[Section] = field(default_factory=list)
    items: dict[str, Item] = field(default_factory=dict)
    phone: str | None = None
    header_lines: list[str] = field(default_factory=list)
    raw_text: str = ""

    def item(self, code: str) -> Item | None:
        return self.items.get(code)

    def amount(self, code: str) -> float | None:
        item = self.items.get(code)
        return item.total() if item else None

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("raw_text", None)
        return data


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    code: str | None = None
    params: dict = field(default_factory=dict)
    internal: bool = False  # True - robotning o'z muammosi, korxonaga yozilmaydi
    text: str = ""          # comment_generator to'ldiradi

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "code": self.code,
            "params": self.params,
            "internal": self.internal,
            "text": self.text,
        }


@dataclass
class ValidationResult:
    decision: Decision
    findings: list[Finding]
    comment: str

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

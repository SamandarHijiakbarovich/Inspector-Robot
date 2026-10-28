"""Hisobot oynasining matnini (innerText) tuzilmali Report obyektiga aylantiradi.

Parser ataylab HTML'ga emas, matnga tayanadi: sayt dizayni o'zgarsa ham savol kodlari
(3.1, 3.1a ...) va qiymatlar tartibi saqlansa, parser ishlashda davom etadi.

Kutilayotgan matn ko'rinishi (oynadan olingan innerText):

    3
    Daromadlar
    3.1
    2025-yildagi jami aylanmangizni kiriting (...)
    234.2 mln so'm
    ...
    4.1
    Ishlab chiqarish xomashyosi va materiallar zaxiralari qiymati
    267.7
    2025 yil boshiga
    370.1
    2025 yil oxiriga
"""
from __future__ import annotations

import re

from ..validator.models import Item, Report, ReportMeta, Section, Value, PERIOD_RE
from .normalize import is_unit, normalize, parse_amount, parse_label_amount, clean_label

CODE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})([a-z])?$")
CODE_INLINE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2}[a-z]?)\s+(.{12,})$")
SECTION_RE = re.compile(r"^(\d{1,2})$")
SECTION_INLINE_RE = re.compile(r"^(\d{1,2})\s+([^\d\s].{2,60})$")
PHONE_QUESTION_RE = re.compile(r"telefon raqam", re.I)
PHONE_RE = re.compile(r"^\+?998[\s\-()]*\d{2}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}$")
FOOTER_RE = re.compile(r"^STIR\s*\(INN\)\s*:\s*(\d*)", re.I)
STATUS_WORDS = ("yangi", "jarayonda", "qabul qilingan", "qaytarilgan")
DECORATION = {"✓", "✔", "×", "avtomatik"}


def looks_like_question(s: str) -> bool:
    return (
        len(s) >= 12
        and sum(c.isalpha() for c in s) >= 8
        and parse_amount(s) is None
        and not is_unit(s)
    )


def _is_title(s: str) -> bool:
    return 3 <= len(s) <= 60 and s[0].isalpha() and s[0].isupper() and not is_unit(s)


def _code_of(line: str) -> tuple[str, str] | None:
    """Qatordagi savol kodini (major, to'liq kod) qaytaradi."""
    m = CODE_RE.match(line)
    if m:
        return m[1], line
    m = CODE_INLINE_RE.match(line)
    if m:
        return m[1], f"{m[1]}.{m[2]}"
    return None


def _section_at(lines: list[str], i: int) -> tuple[Section, int] | None:
    line = lines[i]
    nxt = lines[i + 1] if i + 1 < len(lines) else ""
    nxt2 = lines[i + 2] if i + 2 < len(lines) else ""
    m = SECTION_RE.match(line)
    if m and _is_title(nxt):
        code = _code_of(nxt2)
        if code and code[0] == m[1]:
            return Section(int(m[1]), nxt), 2
    m = SECTION_INLINE_RE.match(line)
    if m and _is_title(m[2]):
        code = _code_of(nxt)
        if code and code[0] == m[1]:
            return Section(int(m[1]), m[2]), 1
    return None


def _item_at(lines: list[str], i: int, section: Section | None) -> tuple[str, str, int] | None:
    line = lines[i]
    nxt = lines[i + 1] if i + 1 < len(lines) else ""
    m = CODE_RE.match(line)
    if m and looks_like_question(nxt) and (section is None or int(m[1]) == section.number):
        return line, nxt, 2
    m = CODE_INLINE_RE.match(line)
    if m and looks_like_question(m[3]) and (section is None or int(m[1]) == section.number):
        return f"{m[1]}.{m[2]}", m[3], 1
    return None


def _split_footer(lines: list[str]) -> tuple[list[str], list[str]]:
    """Oyna pastidagi "Yangi / STIR (INN): ... / Olish" blokini ajratadi."""
    idx = None
    for i in range(len(lines) - 1, -1, -1):
        if FOOTER_RE.match(lines[i]):
            idx = i
            break
    if idx is None:
        return lines, []
    start = idx
    for j in range(idx - 1, max(idx - 3, -1), -1):
        if lines[j].lower() in STATUS_WORDS:
            start = j
            break
    return lines[:start], lines[start:]


def _apply_footer(meta: ReportMeta, footer: list[str]) -> None:
    if not footer:
        return
    if footer[0].lower() in STATUS_WORDS:
        meta.status = footer[0]
        if len(footer) > 1 and not FOOTER_RE.match(footer[1]):
            meta.assigned_inspector = footer[1]
    for line in footer:
        m = FOOTER_RE.match(line)
        if m and m[1] and not meta.inn:
            meta.inn = m[1]


def parse_answers(lines: list[str]) -> tuple[list[Value], list[str]]:
    """Savoldan keyingi qatorlarni qiymatlar (son+birlik+yorliq) va matnli javoblarga ajratadi."""
    values: list[Value] = []
    texts: list[str] = []
    pending: str | None = None  # keyingi songa yorliq bo'lishi mumkin bo'lgan matn
    for ln in lines:
        amt = parse_amount(ln)
        if amt:
            values.append(Value(amount=amt[0], unit=amt[1], label=pending))
            pending = None
            continue
        if is_unit(ln) and values and values[-1].unit is None:
            values[-1].unit = ln
            continue
        if PERIOD_RE.search(ln) and len(ln) < 40 and values and values[-1].label is None:
            values[-1].label = ln
            continue
        la = parse_label_amount(ln)
        if la:
            if pending is not None:
                texts.append(pending)
                pending = None
            values.append(Value(amount=la[1], unit=la[2], label=la[0]))
            continue
        label = clean_label(ln)
        if not label:  # "—", "•" kabi bezak qatorlar
            continue
        if pending is not None:
            texts.append(pending)
        pending = label
    if pending is not None:
        texts.append(pending)
    return values, texts


def parse_report(text: str, meta: ReportMeta | None = None) -> Report:
    meta = meta or ReportMeta()
    # "✓" - bo'lim sarlavhasi yonidagi belgi; "avtomatik" - foiz maydonlari yonidagi yozuv
    lines = [ln for ln in (normalize(x) for x in text.splitlines()) if ln and ln not in DECORATION]
    body, footer = _split_footer(lines)
    _apply_footer(meta, footer)

    report = Report(meta=meta, raw_text=text)
    section: Section | None = None
    raw_items: list[tuple[str, str, Section | None, list[str]]] = []
    current: list[str] | None = None
    phone_pending = False

    i = 0
    while i < len(body):
        found_section = _section_at(body, i)
        if found_section:
            section, step = found_section
            report.sections.append(section)
            current = None
            i += step
            continue
        found_item = _item_at(body, i, section)
        if found_item:
            code, question, step = found_item
            current = []
            raw_items.append((code, question, section, current))
            i += step
            continue

        line = body[i]
        if PHONE_QUESTION_RE.search(line):
            phone_pending = True
            current = None
        elif phone_pending or PHONE_RE.match(line):
            report.phone = line
            phone_pending = False
        elif current is not None:
            current.append(line)
        else:
            report.header_lines.append(line)
        i += 1

    for code, question, sec, item_lines in raw_items:
        values, texts = parse_answers(item_lines)
        key = code
        n = 2
        while key in report.items:  # takrorlangan kod bo'lsa yo'qotmaymiz
            key = f"{code}#{n}"
            n += 1
        report.items[key] = Item(
            code=code,
            question=question,
            section=sec.title if sec else None,
            values=values,
            texts=texts,
        )
    return report

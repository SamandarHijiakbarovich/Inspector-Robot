"""Matnni normallashtirish va sonlarni ajratib olish yordamchilari."""
from __future__ import annotations

import re

# O'zbek tutuq belgisining turli ko'rinishlarini (ʻ ʼ ‘ ’ `) bitta "'" ga keltiramiz
_TRANSLATE = str.maketrans({
    "ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "`": "'", "´": "'",
    " ": " ", " ": " ", " ": " ",
})
_SPACES = re.compile(r"[ \t]+")

_NUM = r"-?\d{1,3}(?: \d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?"
AMOUNT_RE = re.compile(rf"^(?P<num>{_NUM})\s*(?P<rest>.*)$")
LABEL_AMOUNT_RE = re.compile(
    rf"^(?P<label>.*?[^\d\s].*?)\s*[—–\-:]?\s+(?P<num>{_NUM})\s*"
    r"(?P<unit>(?:mln|mlrd|ming)\.?\s*so'm|so'm)$",
    re.I,
)
UNIT_RE = re.compile(
    r"^(?:(?:mln|mlrd|ming)\.?\s*)?so'm$|^(?:dona|kishi|nafar|ta|ga|gektar|tonna|%)$", re.I
)


def normalize(text: str) -> str:
    return _SPACES.sub(" ", text.translate(_TRANSLATE)).strip()


def to_number(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def is_unit(s: str) -> bool:
    return bool(UNIT_RE.match(s.strip()))


def parse_amount(line: str) -> tuple[float, str | None] | None:
    """'234.2 mln so'm' -> (234.2, "mln so'm"); '0' -> (0.0, None); boshqa matn -> None."""
    m = AMOUNT_RE.match(line.strip())
    if not m:
        return None
    if re.fullmatch(r"0\d+", m["num"]):
        return None  # "01491" - OKED kodi, son emas
    rest = m["rest"].strip()
    if rest and not is_unit(rest):
        return None
    return to_number(m["num"]), rest or None


def parse_label_amount(line: str) -> tuple[str, float, str] | None:
    """'• Soliqlar ... — 187.5 mln so'm' -> ("Soliqlar ...", 187.5, "mln so'm")."""
    m = LABEL_AMOUNT_RE.match(line.strip())
    if not m:
        return None
    return clean_label(m["label"]), to_number(m["num"]), m["unit"]


def clean_label(s: str) -> str:
    return s.strip().lstrip("•·*-–— ").rstrip(" —–-:").strip()


def format_amount(x: float | None) -> str:
    """234.2 -> '234.2', 2.0 -> '2', 1234.5 -> '1 234.5'."""
    if x is None:
        return "—"
    r = round(x, 1)
    s = f"{int(r):,}" if r == int(r) else f"{r:,.1f}"
    return s.replace(",", " ")

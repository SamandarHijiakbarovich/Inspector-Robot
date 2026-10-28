"""Loyiha sozlamalari. Qiymatlar .env fayldan yoki muhit o'zgaruvchilaridan o'qiladi."""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _read_env_file(path: Path) -> None:
    """Oddiy KEY=VALUE formatidagi .env faylni o'qiydi (python-dotenv'siz)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "ha", "on")


def _list(name: str, default: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    base_url: str
    lang: str
    inspector_id: str
    org_inn: str
    form_types: tuple[str, ...]
    sector: str
    opf_group: str
    tabs: tuple[str, ...]
    mode: str
    auto_accept: bool
    auto_reject: bool
    manual_take: bool
    click_site_check: bool
    max_actions_per_run: int
    max_reports: int      # 0 = cheklovsiz; 1 = faqat bitta hisobotni ko'rib to'xtash
    only_inn: str         # bo'sh bo'lmasa - faqat shu STIR hisoboti
    confirm_each: bool    # live rejimda har bir Qabul/Qaytarish oldidan terminalda so'rash
    delay_min: float
    delay_max: float
    browser_channel: str
    headless: bool
    timeout_ms: int
    auto_login: bool
    username: str
    password: str
    accept_text: str
    comment_max_len: int
    sum_tolerance: float
    site_warning_action: str  # manual | reject - saytning sariq ogohlantirishi bo'lsa

    def validate_kwargs(self) -> dict:
        """validate() ga uzatiladigan sozlamalar (robot, dump va check bir xil ishlashi uchun)."""
        return {
            "tolerance": self.sum_tolerance,
            "accept_text": self.accept_text,
            "max_len": self.comment_max_len,
            "site_warning_action": self.site_warning_action,
        }
    data_dir: Path

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    @property
    def profile_dir(self) -> Path:
        return self.data_dir / "browser_profile"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "robot.db"

    @property
    def dump_dir(self) -> Path:
        return self.data_dir / "dumps"

    @property
    def screens_dir(self) -> Path:
        return self.data_dir / "screens"

    @property
    def home_url(self) -> str:
        return f"{self.base_url}/{self.lang}/inspector/"

    def reports_url(self, form_type: str) -> str:
        return (
            f"{self.base_url}/{self.lang}/inspector/{self.inspector_id}/reports"
            f"?soato=&oked=&opf=&inn=&opf_group={self.opf_group}&sector={self.sector}&form_type={form_type}"
        )

    @property
    def all_reports_url(self) -> str:
        # "Barchasi" - har qanday shakl/bo'limdan STIR bo'yicha qidirish uchun
        return f"{self.base_url}/{self.lang}/inspector/reports/all"

    def replace(self, **changes) -> "Settings":
        return dataclasses.replace(self, **changes)


def load_settings(env_file: Path | None = None) -> Settings:
    _read_env_file(env_file or BASE_DIR / ".env")
    mode = os.getenv("ROBOT_MODE", "dry_run").strip().lower()
    if mode not in ("dry_run", "live"):
        raise ValueError(f"ROBOT_MODE noto'g'ri: {mode!r} (dry_run yoki live bo'lishi kerak)")
    return Settings(
        base_url=os.getenv("BASE_URL", "https://inspektor.stat.uz").rstrip("/"),
        lang=os.getenv("SITE_LANG", "uz"),
        inspector_id=os.getenv("INSPECTOR_ID", "1"),
        org_inn=os.getenv("ORG_INN", ""),
        form_types=_list("FORM_TYPES", "685"),
        sector=os.getenv("SECTOR", "agriculture"),
        opf_group=os.getenv("OPF_GROUP", ""),
        tabs=_list("TABS", "new"),
        mode=mode,
        auto_accept=_bool("AUTO_ACCEPT", True),
        auto_reject=_bool("AUTO_REJECT", False),
        manual_take=_bool("MANUAL_TAKE", False),
        click_site_check=_bool("CLICK_SITE_CHECK", True),
        max_actions_per_run=int(os.getenv("MAX_ACTIONS_PER_RUN", "20")),
        max_reports=int(os.getenv("MAX_REPORTS", "0")),
        only_inn=os.getenv("ONLY_INN", ""),
        confirm_each=_bool("CONFIRM_EACH", True),
        delay_min=float(os.getenv("DELAY_MIN", "1.5")),
        delay_max=float(os.getenv("DELAY_MAX", "4.0")),
        browser_channel=os.getenv("BROWSER_CHANNEL", "msedge"),
        headless=_bool("HEADLESS", False),
        timeout_ms=int(os.getenv("TIMEOUT_MS", "20000")),
        auto_login=_bool("AUTO_LOGIN", False),
        username=os.getenv("LOGIN_USERNAME", ""),
        password=os.getenv("LOGIN_PASSWORD", ""),
        accept_text=os.getenv("ACCEPT_TEXT", "Tizim tomonidan avtomatik tekshirildi va qabul qilindi."),
        comment_max_len=int(os.getenv("COMMENT_MAX_LEN", "2000")),
        sum_tolerance=float(os.getenv("SUM_TOLERANCE", "0.1")),
        site_warning_action=os.getenv("SITE_WARNING_ACTION", "manual").strip().lower(),
        data_dir=Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))),
    )

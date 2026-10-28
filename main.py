"""Inspektor robot - buyruqlar:

  python main.py login                 # bir marta: brauzerda o'zingiz kirasiz, sessiya saqlanadi
  python main.py dump --form 685       # kalibrlash: ro'yxat va 1-hisobotni faylga saqlash (hech narsa bosilmaydi)
  python main.py check hisobot.txt     # nusxalangan hisobot matnini oflayn tekshirish
  python main.py run --limit 1         # faqat BITTA hisobotni tekshirib, natijani ko'rsatib to'xtash
  python main.py run --inn 305658996   # faqat shu STIR hisobotini tekshirish
  python main.py run --mode live --limit 1   # bitta hisobot, Qabul/Qaytarish oldidan "ha/yo'q" so'raydi
  python main.py run                   # bir marta ishga tushirish (.env dagi ROBOT_MODE bo'yicha)
  python main.py run --loop 300        # har 300 soniyada takrorlash
  python main.py dashboard             # http://127.0.0.1:8000 boshqaruv paneli
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path


def _ensure_venv() -> None:
    """Tizimdagi python bilan chaqirilsa, o'zini .venv ichidagi python bilan qayta ishga tushiradi."""
    root = Path(__file__).resolve().parent / ".venv"
    venv_python = root / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = root / "bin" / "python"
    if venv_python.exists() and Path(sys.prefix).resolve() != root.resolve():
        sys.exit(subprocess.call([str(venv_python), *sys.argv]))


_ensure_venv()

from inspektor_bot.config import load_settings  # noqa: E402


def _setup_logging(settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.data_dir / "robot.log", encoding="utf-8"),
        ],
    )


def cmd_check(args, settings) -> int:
    from inspektor_bot.parsing import parse_report
    from inspektor_bot.validator import validate
    from inspektor_bot.validator.models import ReportMeta

    text = Path(args.file).read_text(encoding="utf-8")
    report = parse_report(text, ReportMeta(form_type=args.form, opf=args.opf or ""))
    result = validate(report, **settings.validate_kwargs())
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    print(f"Savollar: {len(report.items)} ta ({', '.join(report.items)})")
    print(f"Qaror: {result.decision.value}")
    for f in result.findings:
        print(f"  [{f.severity.value}{' ichki' if f.internal else ''}] {f.code + ': ' if f.code else ''}{f.text}")
    print("\n--- Izoh ---")
    print(result.comment or "(bo'sh)")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="inspektor.stat.uz hisobot tekshiruvchi robot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="Brauzerda qo'lda kirish va sessiyani saqlash")

    p = sub.add_parser("dump", help="Ro'yxat va hisobot oynasini faylga saqlash")
    p.add_argument("--form", default=None, help="form_type (standart: FORM_TYPES ning birinchisi)")
    p.add_argument("--tab", default="new", choices=["new", "mine", "accepted", "rejected", "all"])
    p.add_argument("--row", type=int, default=1, help="Nechanchi qatorni ochish")

    p = sub.add_parser("dump-annual", help="Yillik 1-fx hisobotini STIR bo'yicha ochib faylga saqlash")
    p.add_argument("--inn", required=True, help="Korxona STIR raqami")

    p = sub.add_parser("check", help="Hisobot matnini oflayn tekshirish")
    p.add_argument("file")
    p.add_argument("--form", default="685")
    p.add_argument("--opf", default="", help="masalan 130 (fermer xo'jaligi)")
    p.add_argument("--json", action="store_true", help="Parser natijasini ham chiqarish")
    p.add_argument("--site-warning", choices=["manual", "reject"],
                   help="Sayt ogohlantirishi bo'lsa: manual - inspektorga, reject - qaytarish")

    p = sub.add_parser("run", help="Robotni ishga tushirish")
    p.add_argument("--mode", choices=["dry_run", "live"], help=".env dagi ROBOT_MODE ni almashtirish")
    p.add_argument("--loop", type=int, metavar="SONIYA", help="Har N soniyada takrorlash")
    p.add_argument("--limit", type=int, metavar="N", help="Faqat N ta hisobotni ko'rib to'xtash (masalan 1)")
    p.add_argument("--inn", metavar="STIR", help="Faqat shu STIR dagi hisobotni tekshirish")
    p.add_argument("--no-confirm", action="store_true",
                   help="live rejimda Qabul/Qaytarish oldidan so'ramaslik (ishonch hosil qilgandan keyin)")

    p = sub.add_parser("dashboard", help="Boshqaruv panelini ishga tushirish")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)

    sub.add_parser("gui", help="Tugmali oyna (PowerShell shart emas)")

    args = parser.parse_args()
    settings = load_settings()

    if args.cmd == "check":
        if args.site_warning:
            settings = settings.replace(site_warning_action=args.site_warning)
        return cmd_check(args, settings)

    if args.cmd == "gui":
        from inspektor_bot.gui import main as gui_main
        gui_main()  # o'z log sozlamasini qiladi (oyna + fayl)
        return 0

    _setup_logging(settings)

    if args.cmd == "login":
        from inspektor_bot.robot.auth import interactive_login
        interactive_login(settings)
    elif args.cmd == "dump":
        from inspektor_bot.robot.dump import dump
        dump(settings, args.form or settings.form_types[0], args.tab, args.row)
    elif args.cmd == "dump-annual":
        from inspektor_bot.robot.dump import dump_annual
        dump_annual(settings, args.inn.strip())
    elif args.cmd == "run":
        from inspektor_bot.robot.runner import Robot
        from inspektor_bot.storage import Database
        if args.mode:
            settings = settings.replace(mode=args.mode)
        if args.limit:
            settings = settings.replace(max_reports=args.limit)
        if args.inn:
            settings = settings.replace(only_inn=args.inn.strip())
        if args.no_confirm:
            settings = settings.replace(confirm_each=False)
        robot = Robot(settings, Database(settings.db_path))
        if args.loop:
            robot.run_forever(args.loop)
        else:
            robot.run_once()
    elif args.cmd == "dashboard":
        import uvicorn
        uvicorn.run("inspektor_bot.dashboard.server:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())

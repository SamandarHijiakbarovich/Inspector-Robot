"""Inspektor boshqaruv paneli: robot nimani ko'rdi, nima topdi, nima qildi."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import load_settings
from ..storage import Database

DECISION_LABELS = {"ACCEPT": "Xato yo'q", "REJECT": "Xato bor", "MANUAL": "Inspektor ko'rsin"}
ACTION_LABELS = {
    "dry_run": "Sinov rejimi: saytda hech narsa bosilmadi",
    "accepted": "Qabul qilindi",
    "rejected": "Qaytarildi",
    "taken_manual": "Olindi, inspektorni kutmoqda",
    "skipped": "O'tkazib yuborildi",
    "skipped_limit": "Limit tugadi",
    "not_editable": "Boshqa inspektorda",
    "failed": "Xatolik",
    "declined": "Inspektor rad etdi, bo'shatildi",
}
PAGE_SIZE = 50

settings = load_settings()
db = Database(settings.db_path)
app = FastAPI(title="Inspektor robot")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals.update(DECISION_LABELS=DECISION_LABELS, ACTION_LABELS=ACTION_LABELS,
                             mode=settings.mode)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, decision: str | None = None, q: str | None = None, page: int = 1):
    page = max(page, 1)
    rows, total = db.list_reports(decision or None, q or None, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    return templates.TemplateResponse(request, "index.html", {
        "rows": rows, "total": total, "page": page, "pages": max(1, -(-total // PAGE_SIZE)),
        "decision": decision or "", "q": q or "", "stats": db.stats(),
        "events": db.recent_events(30),
    })


@app.get("/report/{report_id}", response_class=HTMLResponse)
def report_detail(request: Request, report_id: int):
    row = db.get_report(report_id)
    if row is None:
        raise HTTPException(404, "Hisobot topilmadi")
    return templates.TemplateResponse(request, "report.html", {"r": row})


@app.get("/runs", response_class=HTMLResponse)
def runs(request: Request):
    return templates.TemplateResponse(request, "runs.html", {"runs": db.list_runs(50)})


@app.get("/api/stats")
def api_stats():
    return db.stats()

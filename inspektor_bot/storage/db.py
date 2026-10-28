"""SQLite: robot ishga tushirishlari, ko'rilgan hisobotlar va loglar."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    mode TEXT,
    processed INTEGER DEFAULT 0,
    accepted INTEGER DEFAULT 0,
    rejected INTEGER DEFAULT 0,
    manual INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    note TEXT
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_key TEXT UNIQUE NOT NULL,
    run_id INTEGER,
    form_type TEXT,
    inn TEXT,
    org_name TEXT,
    opf TEXT,
    soato TEXT,
    submitted_at TEXT,
    decision TEXT,
    action TEXT,
    comment TEXT,
    findings_json TEXT,
    data_json TEXT,
    raw_text TEXT,
    site_check_text TEXT,
    error TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    ts TEXT,
    level TEXT,
    report_key TEXT,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_decision ON reports(decision);
CREATE INDEX IF NOT EXISTS idx_reports_inn ON reports(inn);
"""

# Bu amallardan keyin hisobot qayta ko'rilmaydi
FINAL_ACTIONS = ("accepted", "rejected")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def _exec(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    # ---------- runs ----------

    def start_run(self, mode: str) -> int:
        return self._exec("INSERT INTO runs(started_at, mode) VALUES (?, ?)", (now(), mode)).lastrowid

    def finish_run(self, run_id: int, counters: dict, note: str = "") -> None:
        def c(*keys) -> int:
            return sum(counters.get(k, 0) for k in keys)
        self._exec(
            "UPDATE runs SET finished_at=?, processed=?, accepted=?, rejected=?, manual=?, failed=?, note=? WHERE id=?",
            # qaror hisoblagichlari "accept"/"reject"/"manual" kalitlarida keladi
            (now(), c("processed"), c("accepted", "accept"), c("rejected", "reject"),
             c("manual"), c("failed"), note, run_id),
        )

    # ---------- reports ----------

    def upsert_report(self, rec: dict) -> None:
        rec = {
            "run_id": None, "form_type": "", "inn": "", "org_name": "", "opf": "", "soato": "",
            "submitted_at": "", "decision": None, "action": None, "comment": "", "findings": [],
            "data": {}, "raw_text": "", "site_check_text": "", "error": None, **rec,
        }
        rec["findings_json"] = json.dumps(rec.pop("findings"), ensure_ascii=False)
        rec["data_json"] = json.dumps(rec.pop("data"), ensure_ascii=False)
        rec["ts"] = now()
        self._exec(
            """
            INSERT INTO reports(report_key, run_id, form_type, inn, org_name, opf, soato, submitted_at,
                decision, action, comment, findings_json, data_json, raw_text, site_check_text, error,
                created_at, updated_at)
            VALUES (:report_key, :run_id, :form_type, :inn, :org_name, :opf, :soato, :submitted_at,
                :decision, :action, :comment, :findings_json, :data_json, :raw_text, :site_check_text, :error,
                :ts, :ts)
            ON CONFLICT(report_key) DO UPDATE SET
                run_id=excluded.run_id, org_name=excluded.org_name, opf=excluded.opf, soato=excluded.soato,
                decision=excluded.decision, action=excluded.action, comment=excluded.comment,
                findings_json=excluded.findings_json, data_json=excluded.data_json,
                raw_text=excluded.raw_text, site_check_text=excluded.site_check_text,
                error=excluded.error, updated_at=excluded.updated_at
            """,
            rec,
        )

    def is_final(self, report_key: str) -> bool:
        rows = self._all("SELECT action FROM reports WHERE report_key=?", (report_key,))
        return bool(rows) and rows[0]["action"] in FINAL_ACTIONS

    def list_reports(self, decision: str | None = None, q: str | None = None,
                     limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        where, params = [], []
        if decision:
            where.append("decision=?")
            params.append(decision)
        if q:
            where.append("(inn LIKE ? OR org_name LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        total = self._all(f"SELECT COUNT(*) AS n FROM reports {clause}", tuple(params))[0]["n"]
        rows = self._all(
            f"SELECT id, report_key, form_type, inn, org_name, opf, submitted_at, decision, action, "
            f"error, updated_at FROM reports {clause} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        return rows, total

    def get_report(self, report_id: int) -> dict | None:
        rows = self._all("SELECT * FROM reports WHERE id=?", (report_id,))
        if not rows:
            return None
        row = rows[0]
        row["findings"] = json.loads(row.pop("findings_json") or "[]")
        row["data"] = json.loads(row.pop("data_json") or "{}")
        return row

    def stats(self) -> dict:
        by_decision = {r["decision"]: r["n"] for r in self._all(
            "SELECT decision, COUNT(*) AS n FROM reports GROUP BY decision")}
        by_action = {r["action"]: r["n"] for r in self._all(
            "SELECT action, COUNT(*) AS n FROM reports GROUP BY action")}
        today = self._all("SELECT COUNT(*) AS n FROM reports WHERE updated_at >= date('now','localtime')")[0]["n"]
        return {"by_decision": by_decision, "by_action": by_action, "today": today,
                "total": sum(by_decision.values())}

    # ---------- runs / events ----------

    def list_runs(self, limit: int = 30) -> list[dict]:
        return self._all("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))

    def log(self, run_id: int | None, level: str, message: str, report_key: str | None = None) -> None:
        self._exec("INSERT INTO events(run_id, ts, level, report_key, message) VALUES (?,?,?,?,?)",
                   (run_id, now(), level, report_key, message))

    def recent_events(self, limit: int = 100) -> list[dict]:
        return self._all("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))

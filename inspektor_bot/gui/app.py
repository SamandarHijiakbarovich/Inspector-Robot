"""Inspektor uchun oddiy oyna (PowerShell shart emas).

Tugmalar: Kirish, Sinov, Ishga tushirish, To'xtatish, Dashboard ochish.
Robot va kirish alohida ipda ishlaydi, shuning uchun oyna qotib qolmaydi.
Qabul/Qaytarishni tasdiqlash oyna ichida — "Ha" / "Yo'q" tugmalari bilan.
"""
from __future__ import annotations

import logging
import queue
import threading
import webbrowser
from tkinter import BooleanVar, Tk, scrolledtext, messagebox
from tkinter import ttk

from ..config import Settings, load_settings
from ..storage import Database
from ..validator import Decision

BG = "#f4f6f9"
TITLE = "Inspektor robot — hisobotlarni avtomatik tekshirish"


class GuiLogHandler(logging.Handler):
    def __init__(self, sink: "queue.Queue[tuple[str, str]]"):
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.sink.put(("log", self.format(record)))
        except Exception:
            pass


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.settings = load_settings()
        self.db = Database(self.settings.db_path)
        self.ui_queue: "queue.Queue[tuple]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.robot = None
        self.confirm_answer: "queue.Queue[str]" = queue.Queue(maxsize=1)
        self.live_var = BooleanVar(value=self.settings.is_live)
        self._build()
        self._attach_logging()
        self.root.after(100, self._drain)

    # ---------- UI qurilishi ----------

    def _build(self) -> None:
        self.root.title(TITLE)
        self.root.geometry("920x640")
        self.root.configure(bg=BG)

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        self.btn_login = ttk.Button(top, text="1. Kirish (OneID)", command=self.on_login)
        self.btn_test = ttk.Button(top, text="2. Sinov (bosilmaydi)", command=lambda: self.on_run("dry_run"))
        self.btn_run = ttk.Button(top, text="3. Ishga tushirish", command=lambda: self.on_run("live"))
        self.btn_stop = ttk.Button(top, text="To'xtatish", command=self.on_stop, state="disabled")
        self.btn_dash = ttk.Button(top, text="Dashboard", command=self.on_dashboard)
        for b in (self.btn_login, self.btn_test, self.btn_run, self.btn_stop, self.btn_dash):
            b.pack(side="left", padx=4)

        self.status = ttk.Label(self.root, text="Tayyor. Avval «Kirish» tugmasini bosing.",
                                padding=(12, 4), background=BG)
        self.status.pack(fill="x")

        # Tasdiqlash paneli (kerak bo'lganda ko'rinadi)
        self.confirm_frame = ttk.LabelFrame(self.root, text="Robot javobingizni kutyapti", padding=10)
        self.confirm_text = scrolledtext.ScrolledText(self.confirm_frame, height=10, wrap="word",
                                                       font=("Consolas", 9))
        self.confirm_text.pack(fill="both", expand=True)
        row = ttk.Frame(self.confirm_frame)
        row.pack(fill="x", pady=(8, 0))
        self.btn_yes = ttk.Button(row, text="Ha, bajar", command=lambda: self._answer("ha"))
        self.btn_no = ttk.Button(row, text="Yo'q, o'tkaz", command=lambda: self._answer("yo'q"))
        self.btn_qstop = ttk.Button(row, text="To'xtatish", command=lambda: self._answer("q"))
        for b in (self.btn_yes, self.btn_no, self.btn_qstop):
            b.pack(side="left", padx=4)

        logf = ttk.LabelFrame(self.root, text="Robot jurnali", padding=6)
        logf.pack(fill="both", expand=True, padx=10, pady=10)
        self.logbox = scrolledtext.ScrolledText(logf, wrap="word", font=("Consolas", 9), state="disabled")
        self.logbox.pack(fill="both", expand=True)

    def _attach_logging(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        gui_handler = GuiLogHandler(self.ui_queue)
        gui_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))
        file_handler = logging.FileHandler(self.settings.data_dir / "robot.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        # Konsolsiz (pythonw) ishlaganda StreamHandler xato beradi - faqat oyna va fayl
        root.handlers = [gui_handler, file_handler]

    # ---------- yordamchi ----------

    def _busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for b in (self.btn_login, self.btn_test, self.btn_run, self.btn_dash):
            b.configure(state=state)
        self.btn_stop.configure(state="normal" if busy else "disabled")

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _append_log(self, text: str) -> None:
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _start_worker(self, target, busy_text: str) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(TITLE, "Avvalgi amal hali tugamadi. Kuting yoki «To'xtatish» ni bosing.")
            return
        self._busy(True)
        self._set_status(busy_text)
        self.worker = threading.Thread(target=self._guard(target), daemon=True)
        self.worker.start()

    def _guard(self, target):
        def wrapper():
            try:
                target()
            except Exception as exc:  # ipdagi xato oynani yiqitmasin
                self.ui_queue.put(("log", f"XATO: {exc!r}"))
                self.ui_queue.put(("error", str(exc)))
            finally:
                self.ui_queue.put(("done", None))
        return wrapper

    # ---------- tugma amallari ----------

    def on_login(self) -> None:
        from ..robot.auth import interactive_login

        def task():
            self.ui_queue.put(("log", "Brauzer ochilmoqda. OneID orqali O'ZINGIZ kiring (parolni faqat "
                                      "OneID oynasiga yozing), keyin tashkilotni tanlang."))
            interactive_login(self.settings)
        self._start_worker(task, "Kirish: brauzer oynasida OneID orqali kiring…")

    def on_run(self, mode: str) -> None:
        from ..robot.runner import Robot

        settings = self.settings.replace(mode=mode)
        label = "Sinov (hech narsa bosilmaydi)" if mode == "dry_run" else "Ishga tushirish (LIVE)"
        if mode == "live":
            if settings.confirm_each:
                warn = ("LIVE rejim: robot haqiqatda «Qabul qilish» va «Qaytarish» tugmalarini bosadi.\n"
                        "Har bir amal oldidan sizdan tasdiq so'raladi.\n\nDavom etamizmi?")
            else:
                warn = ("LIVE rejim — TASDIQSIZ (avtonom).\n\n"
                        "Robot sizdan so'ramasdan O'ZI qabul qiladi va qaytaradi.\n"
                        f"Bu ishga tushirishda ko'pi bilan {settings.max_actions_per_run} ta amal bajaradi.\n"
                        "Robot ishonchsiz bo'lgan hisobotlarni baribir sizga qoldiradi.\n\n"
                        "Mas'uliyat siz nomingizdan bajariladi. Davom etamizmi?")
            if not messagebox.askyesno(TITLE, warn):
                return

        def task():
            self.robot = Robot(settings, self.db, confirm=self._gui_confirm,
                               out=lambda t: self.ui_queue.put(("log", t)))
            counters = self.robot.run_once()
            self.ui_queue.put(("log", f"Tugadi: {counters}"))
            self.robot = None
        self._start_worker(task, label + " — ishlayapti…")

    def on_stop(self) -> None:
        if self.robot is not None:
            self.robot.request_stop()
            self._set_status("To'xtatish so'raldi — joriy hisobot tugagach to'xtaydi.")
        # Agar tasdiq kutilyapti bo'lsa, uni ham to'xtatamiz
        if not self.confirm_answer.full():
            try:
                self.confirm_answer.put_nowait("q")
            except queue.Full:
                pass

    def on_dashboard(self) -> None:
        if getattr(self, "_dash_started", False):
            webbrowser.open("http://127.0.0.1:8000")
            return
        import uvicorn

        def task():
            # Ipda ishga tushirilgani uchun signal_handlers o'chiriladi
            config = uvicorn.Config("inspektor_bot.dashboard.server:app", host="127.0.0.1",
                                    port=8000, log_level="warning")
            server = uvicorn.Server(config)
            server.install_signal_handlers = lambda: None
            self.ui_queue.put(("log", "Dashboard ishga tushdi: http://127.0.0.1:8000"))
            self.ui_queue.put(("open_url", "http://127.0.0.1:8000"))
            server.run()
        self._dash_started = True
        threading.Thread(target=task, daemon=True).start()

    # ---------- tasdiqlash (robot ipidan chaqiriladi) ----------

    def _gui_confirm(self, decision: Decision, comment: str, site_text: str) -> str:
        """Robot ipida bloklaydi, oynada "Ha/Yo'q" bosilishini kutadi."""
        act = "QABUL QILINSINMI" if decision is Decision.ACCEPT else "QAYTARILSINMI"
        text = [f"Robot xulosasi: {act}", ""]
        if site_text:
            text += ["Sayt «Tekshirish» natijasi:", site_text, ""]
        text += ["Saytga yoziladigan izoh:", comment or "(izoh yo'q)"]
        self.ui_queue.put(("confirm_show", (act, "\n".join(text))))
        while not self.confirm_answer.empty():
            self.confirm_answer.get_nowait()
        answer = self.confirm_answer.get()  # bloklaydi
        self.ui_queue.put(("confirm_hide", None))
        return answer

    def _answer(self, value: str) -> None:
        try:
            self.confirm_answer.put_nowait(value)
        except queue.Full:
            pass

    # ---------- UI navbatini bo'shatish (asosiy ip) ----------

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "confirm_show":
                    act, body = payload
                    self.confirm_text.configure(state="normal")
                    self.confirm_text.delete("1.0", "end")
                    self.confirm_text.insert("1.0", body)
                    self.confirm_frame.pack(fill="x", padx=10, before=self.logbox.master)
                    self._set_status(f"Robot kutyapti: hisobot {act}? Izohni ko'rib, tugmani bosing.")
                    self.root.bell()
                elif kind == "confirm_hide":
                    self.confirm_frame.pack_forget()
                elif kind == "open_url":
                    webbrowser.open(payload)
                elif kind == "error":
                    messagebox.showerror(TITLE, payload)
                elif kind == "done":
                    self._busy(False)
                    self._set_status("Tayyor.")
                    self.confirm_frame.pack_forget()
        except queue.Empty:
            pass
        self.root.after(100, self._drain)


def main() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

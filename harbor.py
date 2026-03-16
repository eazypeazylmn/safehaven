"""
================================================================================
Harbor - SafeHaven GUI
================================================================================

Das Haupt-GUI für SafeHaven. Gebaut mit tkinter (in Python eingebaut,
kein extra Install nötig).

Design:
    Dark theme, monospace font, subtile Akzentfarben pro Ereignistyp.

Architektur:
    - Harbor          Hauptfenster – baut alle Widgets auf, verwaltet Bot-Thread
    - _build_stats()  Linke Spalte: Session-Timer + alle Stat-Karten
    - _build_log()    Rechte Spalte: scrollbarer Live-Log mit farbigen Tags
    - _run_bot()      Bot-Loop – läuft in eigenem Thread (GUI friert nicht ein)
    - update_queue    thread-safe Queue für Bot → GUI Kommunikation

Kommunikation Bot → GUI (über update_queue):
    ("log",     message, tag)   → Zeile in den Log schreiben
    ("stat",    key)            → Stat um 1 erhöhen
    ("status",  text)           → Status-Label oben rechts aktualisieren
    ("stopped", None)           → Bot-Thread ist fertig, Buttons zurücksetzen

Debug-Fenster (optional, über Buttons):
    "DEBUG OVERLAY"  → öffnet DebugOverlay (debugtools.py)
    "HSV CALIB"      → öffnet HsvCalibrator (debugtools.py)
    Beide Fenster sind unabhängig und können jederzeit geöffnet/geschlossen werden.

Hinweis zu Drift:
    Der Bot-Thread nutzt current.drift (Singleton aus Current).
    Kein eigenes Drift(config) instanziieren – sonst stimmt der Break-Zähler nicht.

Verwendung:
    python harbor.py
    oder: Doppelklick auf SafeHaven.bat
================================================================================
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
import queue
import time
from datetime import datetime

from tideconfig import TideConfig
from shorewatch import ShoreWatch
from current import Current


# =============================================================================
# Farbpalette – dark theme
# =============================================================================
COLORS = {
    "bg":          "#0e0e0e",
    "bg_panel":    "#151515",
    "bg_card":     "#1c1c1c",
    "border":      "#2a2a2a",
    "accent":      "#4a9eff",
    "accent_dim":  "#1e3f6e",
    "success":     "#3ddc84",
    "warning":     "#f0a500",
    "danger":      "#e05c5c",
    "muted":       "#555555",
    "text_bright": "#f0f0f0",
    "text_dim":    "#777777",
    "log_default": "#8a8a8a",
    "log_cast":    "#4a9eff",
    "log_bite":    "#3ddc84",
    "log_miss":    "#f0a500",
    "log_escaped": "#e05c5c",
    "log_break":   "#bb86fc",
    "log_warn":    "#f0a500",
}


class Harbor(tk.Tk):
    """
    Hauptfenster der SafeHaven GUI.
    Verwaltet Layout, Bot-Thread und die Update-Queue.
    """

    def __init__(self):
        super().__init__()

        self.title("SafeHaven  //  SSC Edition")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.geometry("820x560")

        # Bot-State
        self.bot_running = False
        self.bot_thread = None
        self.update_queue = queue.Queue()

        # ShoreWatch Instanz – wird beim Start erstellt und an Debug-Fenster weitergegeben
        self._shore = None
        self._config = None

        # Referenzen auf Debug-Fenster (damit nicht mehrfach geöffnet werden)
        self._debug_overlay = None
        self._hsv_calibrator = None

        # Session-Stats als tkinter StringVars (auto-update UI)
        self.stats = {
            "waves":   tk.StringVar(value="0"),
            "caught":  tk.StringVar(value="0"),
            "missed":  tk.StringVar(value="0"),
            "escaped": tk.StringVar(value="0"),
            "early":   tk.StringVar(value="0"),
            "rate":    tk.StringVar(value="0.0%"),
            "timer":   tk.StringVar(value="00:00:00"),
            "status":  tk.StringVar(value="IDLE"),
        }

        # Rohe Integer-Werte für Berechnungen
        self._raw = {k: 0 for k in ["waves", "caught", "missed", "escaped", "early"]}
        self._session_start = None

        self._build_ui()
        self._poll_queue()
        self._tick_timer()

    # -------------------------------------------------------------------------
    # UI aufbauen
    # -------------------------------------------------------------------------

    def _build_ui(self):
        """Baut das komplette UI auf (Header, Stats, Log, Controls)."""

        # Header
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(14, 0))

        tk.Label(header, text="⚓  SAFEHAVEN", bg=COLORS["bg"],
                 fg=COLORS["accent"], font=("Courier New", 13, "bold")
                 ).pack(side="left")

        tk.Label(header, text="SSC Edition  //  v1.2.0",
                 bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Courier New", 9)
                 ).pack(side="left", padx=(10, 0), pady=(3, 0))

        self._status_label = tk.Label(
            header, textvariable=self.stats["status"],
            bg=COLORS["bg"], fg=COLORS["muted"],
            font=("Courier New", 9, "bold")
        )
        self._status_label.pack(side="right")

        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=(10, 0))

        # Hauptbereich
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=12)

        left = tk.Frame(main, bg=COLORS["bg"], width=230)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._build_stats(left)

        right = tk.Frame(main, bg=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._build_log(right)

        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x", padx=16)
        self._build_controls()

    def _build_stats(self, parent):
        """Linke Spalte: Session-Timer und alle Stat-Karten."""

        timer_card = tk.Frame(parent, bg=COLORS["bg_card"],
                              highlightbackground=COLORS["border"],
                              highlightthickness=1)
        timer_card.pack(fill="x", pady=(0, 8))

        tk.Label(timer_card, text="SESSION", bg=COLORS["bg_card"],
                 fg=COLORS["text_dim"], font=("Courier New", 7, "bold")
                 ).pack(anchor="w", padx=10, pady=(8, 0))

        tk.Label(timer_card, textvariable=self.stats["timer"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"],
                 font=("Courier New", 22, "bold")
                 ).pack(anchor="w", padx=10, pady=(0, 8))

        cards = [
            ("CASTS",        "waves",   COLORS["text_bright"], "🎣"),
            ("CAUGHT",       "caught",  COLORS["success"],     "🐟"),
            ("MISSES",       "missed",  COLORS["warning"],     "💨"),
            ("ESCAPED",      "escaped", COLORS["danger"],      "🌊"),
            ("EARLY REACTS", "early",   "#bb86fc",             "⚡"),
            ("CATCH RATE",   "rate",    COLORS["accent"],      "📊"),
        ]

        for label, key, color, icon in cards:
            card = tk.Frame(parent, bg=COLORS["bg_card"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            card.pack(fill="x", pady=2)

            inner = tk.Frame(card, bg=COLORS["bg_card"])
            inner.pack(fill="x", padx=10, pady=6)

            tk.Label(inner, text=f"{icon}  {label}",
                     bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                     font=("Courier New", 7, "bold")
                     ).pack(side="left")

            tk.Label(inner, textvariable=self.stats[key],
                     bg=COLORS["bg_card"], fg=color,
                     font=("Courier New", 13, "bold")
                     ).pack(side="right")

    def _build_log(self, parent):
        """Rechte Spalte: scrollbarer Live-Log mit farbigen Tags."""

        tk.Label(parent, text="LIVE LOG", bg=COLORS["bg"],
                 fg=COLORS["text_dim"], font=("Courier New", 7, "bold")
                 ).pack(anchor="w", pady=(0, 4))

        self.log_box = scrolledtext.ScrolledText(
            parent,
            bg=COLORS["bg_panel"], fg=COLORS["log_default"],
            font=("Courier New", 9),
            bd=0, relief="flat", wrap="word",
            state="disabled", cursor="arrow",
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        self.log_box.pack(fill="both", expand=True)

        for tag, color in {
            "cast":    COLORS["log_cast"],
            "bite":    COLORS["log_bite"],
            "miss":    COLORS["log_miss"],
            "escaped": COLORS["log_escaped"],
            "brk":     COLORS["log_break"],
            "warn":    COLORS["log_warn"],
            "dim":     COLORS["log_default"],
            "bright":  COLORS["text_bright"],
        }.items():
            self.log_box.tag_config(tag, foreground=color)

    def _build_controls(self):
        """Untere Leiste: Start/Stop + Debug-Buttons + Failsafe-Hinweis."""

        ctrl = tk.Frame(self, bg=COLORS["bg"])
        ctrl.pack(fill="x", padx=16, pady=10)

        # Start / Stop
        self.btn_start = tk.Button(
            ctrl, text="▶  START",
            bg=COLORS["accent_dim"], fg=COLORS["accent"],
            activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
            font=("Courier New", 10, "bold"),
            bd=0, padx=20, pady=8, cursor="hand2",
            command=self._start_bot
        )
        self.btn_start.pack(side="left")

        self.btn_stop = tk.Button(
            ctrl, text="■  STOP",
            bg="#2a1a1a", fg=COLORS["danger"],
            activebackground=COLORS["danger"], activeforeground=COLORS["bg"],
            font=("Courier New", 10, "bold"),
            bd=0, padx=20, pady=8, cursor="hand2",
            state="disabled",
            command=self._stop_bot
        )
        self.btn_stop.pack(side="left", padx=(8, 0))

        # Debug-Buttons (nur aktiv wenn Bot läuft)
        self.btn_debug = tk.Button(
            ctrl, text="🔍  DEBUG",
            bg=COLORS["bg_card"], fg=COLORS["muted"],
            font=("Courier New", 9),
            bd=0, padx=12, pady=8, cursor="hand2",
            state="disabled",
            command=self._open_debug_overlay
        )
        self.btn_debug.pack(side="left", padx=(16, 0))

        self.btn_hsv = tk.Button(
            ctrl, text="🎨  HSV CALIB",
            bg=COLORS["bg_card"], fg=COLORS["muted"],
            font=("Courier New", 9),
            bd=0, padx=12, pady=8, cursor="hand2",
            state="disabled",
            command=self._open_hsv_calibrator
        )
        self.btn_hsv.pack(side="left", padx=(6, 0))

        tk.Label(ctrl,
                 text="Failsafe: Maus in obere linke Ecke",
                 bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Courier New", 8)
                 ).pack(side="right")

    # -------------------------------------------------------------------------
    # Debug-Fenster öffnen
    # -------------------------------------------------------------------------

    def _open_debug_overlay(self):
        """Öffnet das Debug-Overlay (oder bringt es in den Vordergrund)."""
        from debugtools import DebugOverlay

        if self._debug_overlay and self._debug_overlay.winfo_exists():
            self._debug_overlay.lift()
            return

        if self._shore and self._config:
            self._debug_overlay = DebugOverlay(self, self._shore, self._config)

    def _open_hsv_calibrator(self):
        """Öffnet den HSV-Kalibrator (oder bringt ihn in den Vordergrund)."""
        from debugtools import HsvCalibrator

        if self._hsv_calibrator and self._hsv_calibrator.winfo_exists():
            self._hsv_calibrator.lift()
            return

        if self._config:
            self._hsv_calibrator = HsvCalibrator(self, self._config)

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def _append_log(self, message: str, tag: str):
        """Fügt eine Zeile zum Log-Widget hinzu. Nur im Main-Thread aufrufen."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n", tag)
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def _increment_stat(self, key: str):
        """Erhöht einen numerischen Stat um 1 und aktualisiert die Anzeige."""
        self._raw[key] += 1
        self.stats[key].set(str(self._raw[key]))
        self._recalc_rate()

    def _recalc_rate(self):
        """Berechnet die Catch-Rate aus caught / waves neu."""
        waves = self._raw["waves"]
        if waves > 0:
            self.stats["rate"].set(f"{(self._raw['caught'] / waves * 100):.1f}%")

    # -------------------------------------------------------------------------
    # Queue pollen
    # -------------------------------------------------------------------------

    def _poll_queue(self):
        """
        Verarbeitet alle ausstehenden Nachrichten aus update_queue.
        Wird alle 80ms vom Main-Thread via after() aufgerufen.
        """
        try:
            while True:
                msg = self.update_queue.get_nowait()
                kind = msg[0]

                if kind == "log":
                    self._append_log(msg[1], msg[2])
                elif kind == "stat":
                    self._increment_stat(msg[1])
                elif kind == "status":
                    self.stats["status"].set(msg[1])
                    color = (COLORS["success"] if msg[1] == "RUNNING"
                             else COLORS["danger"] if msg[1] == "STOPPED"
                             else COLORS["muted"])
                    self._status_label.configure(fg=color)
                elif kind == "stopped":
                    self._on_bot_stopped()

        except queue.Empty:
            pass
        finally:
            self.after(80, self._poll_queue)

    # -------------------------------------------------------------------------
    # Timer
    # -------------------------------------------------------------------------

    def _tick_timer(self):
        """Aktualisiert den Session-Timer jede Sekunde."""
        if self._session_start and self.bot_running:
            elapsed = int(time.time() - self._session_start)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.stats["timer"].set(f"{h:02d}:{m:02d}:{s:02d}")
        self.after(1000, self._tick_timer)

    # -------------------------------------------------------------------------
    # Bot starten / stoppen
    # -------------------------------------------------------------------------

    def _start_bot(self):
        """Setzt Stats zurück, erstellt ShoreWatch/Config, startet Bot-Thread."""
        if self.bot_running:
            return

        for k in self._raw:
            self._raw[k] = 0
            self.stats[k].set("0")
        self.stats["rate"].set("0.0%")
        self.stats["timer"].set("00:00:00")

        self.bot_running = True
        self._session_start = time.time()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_debug.configure(state="normal", fg=COLORS["accent"])
        self.btn_hsv.configure(state="normal", fg=COLORS["accent"])

        self.update_queue.put(("status", "RUNNING"))

        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()

    def _stop_bot(self):
        """Setzt bot_running = False – der Bot-Thread prüft das in seiner Loop."""
        self.bot_running = False

    def _on_bot_stopped(self):
        """Wird aufgerufen wenn der Bot-Thread sauber beendet wurde."""
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_debug.configure(state="disabled", fg=COLORS["muted"])
        self.btn_hsv.configure(state="disabled", fg=COLORS["muted"])
        self.update_queue.put(("status", "STOPPED"))

    # -------------------------------------------------------------------------
    # Bot-Loop
    # -------------------------------------------------------------------------

    def _run_bot(self):
        """
        Hauptschleife des Bots – läuft in einem separaten Thread.
        Kommuniziert mit der GUI ausschließlich über self.update_queue.
        Greift auf Drift über current.drift zu (kein eigenes Drift() instanziieren).
        """
        q = self.update_queue
        self._config = TideConfig()
        self._shore = ShoreWatch(self._config)
        current = Current(self._config)
        human = current.drift  # Drift-Singleton aus Current

        def log(msg, tag="dim"):
            ts = datetime.now().strftime("%H:%M:%S")
            q.put(("log", f"[{ts}]  {msg}", tag))

        def stat(key):
            q.put(("stat", key))

        log("Waiting 3 seconds – click into WoW now!", "bright")
        for i in range(3, 0, -1):
            if not self.bot_running:
                break
            log(f"Starting in {i}...", "dim")
            time.sleep(1)

        log("─" * 42, "dim")

        while self.bot_running:
            stat("waves")
            log(f"Wave #{self._raw['waves']}", "bright")

            current.cast()
            log(f"Line cast  (key: '{self._config.CAST_KEY}')", "cast")
            time.sleep(self._config.SETTLE_DRIFT)

            if not self.bot_running:
                break

            buoy = self._shore.find_buoy()
            if buoy is None:
                log("Buoy not spotted – retrying...", "warn")
                time.sleep(1)
                continue

            log(f"Buoy spotted at {buoy}", "cast")

            if human.should_react_early():
                stat("early")
                log("Early reaction – false splash! Recasting.", "brk")
                current.reel_in(buoy)
                time.sleep(self._config.HAUL_DELAY)
                continue

            log("Reading the tide...", "dim")
            bite = self._shore.await_ripple(buoy)

            if not self.bot_running:
                break

            if not bite:
                stat("escaped")
                log("Fish escaped – no bite in time.", "escaped")
                continue

            log("Ripple detected!", "bite")

            if human.should_react_late():
                delay = human.late_reaction_delay()
                log(f"Slow reaction (+{delay:.1f}s)...", "dim")
                time.sleep(delay)

            success = current.reel_in(buoy)

            if not success:
                stat("missed")
                log("Missed the bobber! Recasting.", "miss")
                continue

            stat("caught")
            log(f"Hauled in!  Total: {self._raw['caught']} 🐟", "bite")
            time.sleep(self._config.HAUL_DELAY)

        log("─" * 42, "dim")
        log("SafeHaven docked.", "bright")
        q.put(("stopped", None))


if __name__ == "__main__":
    app = Harbor()
    app.mainloop()

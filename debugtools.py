"""
================================================================================
DebugTools - SafeHaven Debug Windows
================================================================================

Dieses Modul enthält zwei optionale Hilfsfenster die über Buttons
in harbor.py geöffnet werden können:

    1. DebugOverlay     Zeigt live was ShoreWatch auf dem Bildschirm sieht:
                        - Scan View:   Voller SCAN_WATERS Bereich + Buoy-Marker
                        - Ripple View: tide_zone Ausschnitt um den Buoy

    2. HsvCalibrator    Sliders für alle HSV-Farbwerte des Buoys.
                        Änderungen gelten sofort – kein Code-Edit nötig.
                        "Copy"-Button kopiert die Werte als tideconfig.py-Snippet.

Abhängigkeit:
    Pillow (PIL) wird benötigt um OpenCV-Frames in tkinter anzuzeigen.
    Ist in requirements.txt eingetragen.

Datenfluss:
    ShoreWatch → DebugState (thread-safe dict) → DebugOverlay (tkinter after())
    Der Bot-Thread schreibt nur in DebugState, nie direkt in tkinter-Widgets.
================================================================================
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import logging

import cv2
import numpy as np
from PIL import Image, ImageTk

from tideconfig import TideConfig
from shorewatch import ShoreWatch


# =============================================================================
# Farbpalette (passend zu harbor.py)
# =============================================================================
COLORS = {
    "bg":       "#0e0e0e",
    "bg_card":  "#1c1c1c",
    "border":   "#2a2a2a",
    "accent":   "#4a9eff",
    "success":  "#3ddc84",
    "danger":   "#e05c5c",
    "muted":    "#555555",
    "text":     "#d4d4d4",
}


# =============================================================================
# DebugOverlay
# =============================================================================

class DebugOverlay(tk.Toplevel):
    """
    Separates Fenster das live zeigt was ShoreWatch auf dem Bildschirm sieht.

    Zwei Ansichten per Toggle-Button:
        Scan View   - Voller SCAN_WATERS Bereich mit Buoy-Marker (grünes Kreuz)
        Ripple View - tide_zone Ausschnitt um den Buoy (80x80px Region)

    Aktualisiert sich alle 100ms über tkinter after().
    Liest Frames aus debug_state (thread-safe dict) das ShoreWatch befüllt.
    """

    REFRESH_MS = 100  # Aktualisierungsrate in Millisekunden

    def __init__(self, parent, shore: ShoreWatch, config: TideConfig):
        super().__init__(parent)

        self.shore = shore
        self.config = config
        self.log = logging.getLogger(__name__)

        # Ansicht: "scan" oder "ripple"
        self._view_mode = tk.StringVar(value="scan")

        self.title("SafeHaven – Debug Overlay")
        self.configure(bg=COLORS["bg"])
        self.resizable(True, True)

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        """Baut Header, Toggle-Buttons und Canvas auf."""

        # Header mit Toggle
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(header, text="DEBUG OVERLAY",
                 bg=COLORS["bg"], fg=COLORS["accent"],
                 font=("Courier New", 10, "bold")
                 ).pack(side="left")

        # Toggle-Buttons
        btn_frame = tk.Frame(header, bg=COLORS["bg"])
        btn_frame.pack(side="right")

        for label, mode in [("SCAN VIEW", "scan"), ("RIPPLE VIEW", "ripple")]:
            tk.Radiobutton(
                btn_frame, text=label,
                variable=self._view_mode, value=mode,
                bg=COLORS["bg"], fg=COLORS["text"],
                selectcolor=COLORS["bg_card"],
                activebackground=COLORS["bg"],
                font=("Courier New", 8),
                indicatoron=False,
                padx=8, pady=4,
                bd=1, relief="solid"
            ).pack(side="left", padx=2)

        # Status-Label (zeigt Buoy-Koordinaten)
        self._status_var = tk.StringVar(value="Waiting for bot...")
        tk.Label(self, textvariable=self._status_var,
                 bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Courier New", 8)
                 ).pack(padx=10, anchor="w")

        # Canvas für das Frame
        self.canvas = tk.Canvas(self, bg="#000000",
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
        self.canvas.pack(padx=10, pady=(4, 10), fill="both", expand=True)
        self._canvas_image = None  # Referenz halten damit GC es nicht löscht

    def _refresh(self):
        """
        Wird alle REFRESH_MS Millisekunden aufgerufen.
        Liest den aktuellen Debug-State aus ShoreWatch und zeichnet das Frame.
        """
        try:
            state = self.shore.debug_state

            if self._view_mode.get() == "scan":
                self._draw_scan_view(state)
            else:
                self._draw_ripple_view(state)

        except Exception as e:
            self.log.debug(f"Debug overlay refresh error: {e}")
        finally:
            self.after(self.REFRESH_MS, self._refresh)

    def _draw_scan_view(self, state: dict):
        """
        Scan View: Voller SCAN_WATERS Frame mit Buoy-Marker.

        Zeichnet:
            - Grünes Kreuz (+) auf der Buoy-Position
            - Blaues Rechteck für die tide_zone (Ripple-Überwachungsregion)
        """
        frame = state.get("scan_frame")
        if frame is None:
            return

        display = frame.copy()
        buoy = state.get("buoy")

        if buoy is not None:
            bx, by = buoy

            # Offset korrigieren falls SCAN_WATERS gesetzt ist
            if self.config.SCAN_WATERS:
                ox, oy, _, _ = self.config.SCAN_WATERS
                bx -= ox
                by -= oy

            # Grünes Kreuz auf Buoy-Position
            cv2.drawMarker(display, (bx, by), (0, 255, 80),
                           cv2.MARKER_CROSS, markerSize=20, thickness=2)

            # Blaues Rechteck = tide_zone
            r = self.config.RIPPLE_RADIUS
            cv2.rectangle(display,
                          (bx - r, by - r), (bx + r, by + r),
                          (255, 160, 0), 1)

            self._status_var.set(f"Buoy at screen: {state.get('buoy')}  |  tide_zone radius: {r}px")
        else:
            self._status_var.set("No buoy detected")

        self._render_frame(display)

    def _draw_ripple_view(self, state: dict):
        """
        Ripple View: tide_zone Ausschnitt um den Buoy.
        Zeigt den 80x80px Bereich der auf Bewegung überwacht wird.
        """
        frame = state.get("ripple_frame")
        if frame is None:
            self._status_var.set("Waiting for ripple region...")
            return

        # Rahmen um die Region
        display = frame.copy()
        cv2.rectangle(display, (0, 0),
                      (display.shape[1] - 1, display.shape[0] - 1),
                      (255, 160, 0), 2)

        self._status_var.set(f"Ripple zone: {display.shape[1]}x{display.shape[0]}px")
        self._render_frame(display, scale=4)  # Hochskalieren da Region klein ist

    def _render_frame(self, bgr_frame: np.ndarray, scale: float = 1.0):
        """Konvertiert einen OpenCV BGR-Frame in ein tkinter-kompatibles Bild."""
        if scale != 1.0:
            h, w = bgr_frame.shape[:2]
            bgr_frame = cv2.resize(bgr_frame, (int(w * scale), int(h * scale)),
                                   interpolation=cv2.INTER_NEAREST)

        # BGR → RGB für PIL
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        # Canvas-Größe anpassen
        self.canvas.configure(width=pil_img.width, height=pil_img.height)

        tk_img = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=tk_img)
        self._canvas_image = tk_img  # Referenz halten!


# =============================================================================
# HsvCalibrator
# =============================================================================

class HsvCalibrator(tk.Toplevel):
    """
    HSV-Kalibrierungsfenster mit Live-Slidern.

    Zeigt Sliders für alle 4 HSV-Grenzwerte des Buoys:
        SHORE_HUE_LOW_1 / HIGH_1   (Roter Bereich 1, Hue 0-10)
        SHORE_HUE_LOW_2 / HIGH_2   (Roter Bereich 2, Hue 170-180)

    Änderungen gelten sofort – ShoreWatch liest die Werte direkt
    aus dem TideConfig-Objekt das hier live aktualisiert wird.

    "Copy to clipboard"-Button gibt ein fertiges tideconfig.py-Snippet aus.
    """

    def __init__(self, parent, config: TideConfig):
        super().__init__(parent)

        self.config = config
        self.log = logging.getLogger(__name__)

        self.title("SafeHaven – HSV Calibrator")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        # Slider-Variablen initialisieren aus aktueller Config
        self._vars = {
            "low1_h":  tk.IntVar(value=config.SHORE_HUE_LOW_1[0]),
            "low1_s":  tk.IntVar(value=config.SHORE_HUE_LOW_1[1]),
            "low1_v":  tk.IntVar(value=config.SHORE_HUE_LOW_1[2]),
            "high1_h": tk.IntVar(value=config.SHORE_HUE_HIGH_1[0]),
            "high1_s": tk.IntVar(value=config.SHORE_HUE_HIGH_1[1]),
            "high1_v": tk.IntVar(value=config.SHORE_HUE_HIGH_1[2]),
            "low2_h":  tk.IntVar(value=config.SHORE_HUE_LOW_2[0]),
            "low2_s":  tk.IntVar(value=config.SHORE_HUE_LOW_2[1]),
            "low2_v":  tk.IntVar(value=config.SHORE_HUE_LOW_2[2]),
            "high2_h": tk.IntVar(value=config.SHORE_HUE_HIGH_2[0]),
            "high2_s": tk.IntVar(value=config.SHORE_HUE_HIGH_2[1]),
            "high2_v": tk.IntVar(value=config.SHORE_HUE_HIGH_2[2]),
        }

        # Alle Variablen tracen → config live aktualisieren
        for var in self._vars.values():
            var.trace_add("write", self._apply)

        self._build_ui()

    def _build_ui(self):
        """Baut zwei Slider-Gruppen und den Copy-Button auf."""

        tk.Label(self, text="HSV CALIBRATOR",
                 bg=COLORS["bg"], fg=COLORS["accent"],
                 font=("Courier New", 10, "bold")
                 ).pack(padx=14, pady=(12, 6), anchor="w")

        tk.Label(self, text="Änderungen gelten sofort. Roter Federkiel des Bobbers.",
                 bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Courier New", 8)
                 ).pack(padx=14, anchor="w")

        # Gruppe 1: SHORE_HUE_LOW_1 / HIGH_1
        self._slider_group(
            "Red Range 1  (Hue 0–10)",
            [("LOW  H", "low1_h",  0, 10),
             ("LOW  S", "low1_s",  0, 255),
             ("LOW  V", "low1_v",  0, 255),
             ("HIGH H", "high1_h", 0, 10),
             ("HIGH S", "high1_s", 0, 255),
             ("HIGH V", "high1_v", 0, 255)],
        )

        # Gruppe 2: SHORE_HUE_LOW_2 / HIGH_2
        self._slider_group(
            "Red Range 2  (Hue 170–180)",
            [("LOW  H", "low2_h",  160, 180),
             ("LOW  S", "low2_s",  0, 255),
             ("LOW  V", "low2_v",  0, 255),
             ("HIGH H", "high2_h", 160, 180),
             ("HIGH S", "high2_s", 0, 255),
             ("HIGH V", "high2_v", 0, 255)],
        )

        # Copy-Button
        tk.Button(
            self, text="📋  Copy values to clipboard",
            bg=COLORS["bg_card"], fg=COLORS["accent"],
            activebackground=COLORS["border"],
            font=("Courier New", 9), bd=0, padx=12, pady=6,
            cursor="hand2", command=self._copy_to_clipboard
        ).pack(padx=14, pady=(6, 14), anchor="w")

    def _slider_group(self, title: str, sliders: list):
        """Erstellt eine benannte Gruppe von Slidern."""
        frame = tk.Frame(self, bg=COLORS["bg_card"],
                         highlightbackground=COLORS["border"],
                         highlightthickness=1)
        frame.pack(fill="x", padx=14, pady=4)

        tk.Label(frame, text=title,
                 bg=COLORS["bg_card"], fg=COLORS["text"],
                 font=("Courier New", 8, "bold")
                 ).pack(anchor="w", padx=10, pady=(8, 4))

        for label, key, from_, to in sliders:
            row = tk.Frame(frame, bg=COLORS["bg_card"])
            row.pack(fill="x", padx=10, pady=2)

            tk.Label(row, text=label, width=8,
                     bg=COLORS["bg_card"], fg=COLORS["muted"],
                     font=("Courier New", 8), anchor="w"
                     ).pack(side="left")

            tk.Scale(
                row, variable=self._vars[key],
                from_=from_, to=to, orient="horizontal",
                bg=COLORS["bg_card"], fg=COLORS["text"],
                troughcolor=COLORS["border"],
                highlightthickness=0, bd=0,
                length=200, showvalue=True,
                font=("Courier New", 7)
            ).pack(side="left")

        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x", padx=10, pady=(4, 0))

    def _apply(self, *_):
        """Schreibt alle Slider-Werte sofort in das TideConfig-Objekt."""
        v = self._vars
        self.config.SHORE_HUE_LOW_1  = (v["low1_h"].get(),  v["low1_s"].get(),  v["low1_v"].get())
        self.config.SHORE_HUE_HIGH_1 = (v["high1_h"].get(), v["high1_s"].get(), v["high1_v"].get())
        self.config.SHORE_HUE_LOW_2  = (v["low2_h"].get(),  v["low2_s"].get(),  v["low2_v"].get())
        self.config.SHORE_HUE_HIGH_2 = (v["high2_h"].get(), v["high2_s"].get(), v["high2_v"].get())

    def _copy_to_clipboard(self):
        """Kopiert die aktuellen Werte als fertiges tideconfig.py-Snippet."""
        v = self._vars
        snippet = (
            f"# Paste into tideconfig.py:\n"
            f"SHORE_HUE_LOW_1:  tuple = ({v['low1_h'].get()}, {v['low1_s'].get()}, {v['low1_v'].get()})\n"
            f"SHORE_HUE_HIGH_1: tuple = ({v['high1_h'].get()}, {v['high1_s'].get()}, {v['high1_v'].get()})\n"
            f"SHORE_HUE_LOW_2:  tuple = ({v['low2_h'].get()}, {v['low2_s'].get()}, {v['low2_v'].get()})\n"
            f"SHORE_HUE_HIGH_2: tuple = ({v['high2_h'].get()}, {v['high2_s'].get()}, {v['high2_v'].get()})\n"
        )
        self.clipboard_clear()
        self.clipboard_append(snippet)
        self.log.info("HSV values copied to clipboard.")

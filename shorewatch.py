"""
================================================================================
ShoreWatch - SafeHaven Bobber Detection
================================================================================

Dieses Modul ist das Herzstück des Bots.
Es ist verantwortlich für:
    1. find_buoy()      Den roten Federkiel auf dem Bildschirm finden
    2. await_ripple()   Die Splash-Animation erkennen (= Biss)

Technischer Hintergrund:
    - Screenshots werden mit mss gemacht (sehr schnell, nutzt DirectX/X11)
    - OpenCV konvertiert BGR -> HSV für zuverlässige Farberkennung
    - Bewegungserkennung via Frame-Differenz (aktueller Frame vs. vorheriger)

Debug-State:
    ShoreWatch befüllt self.debug_state mit den aktuellen Frames und
    der erkannten Buoy-Position. DebugOverlay (debugtools.py) liest
    daraus – niemals direkt in tkinter schreiben vom Bot-Thread!

    debug_state keys:
        "scan_frame"    np.ndarray  Letzter SCAN_WATERS Screenshot (BGR)
        "ripple_frame"  np.ndarray  Letzter tide_zone Screenshot (BGR)
        "buoy"          tuple|None  Letzte erkannte Buoy-Position (x, y)
================================================================================
"""

import time
import logging
import threading

import cv2
import numpy as np
import mss

from tideconfig import TideConfig


class ShoreWatch:
    """
    Beobachtet den Bildschirm: findet den Buoy (Bobber) und erkennt Ripples (Bisse).

    Attributes:
        debug_state: Thread-safe dict für DebugOverlay.
                     Wird vom Bot-Thread geschrieben, vom Main-Thread gelesen.
    """

    def __init__(self, config: TideConfig):
        self.config = config
        self.log = logging.getLogger(__name__)

        # mss-Instanz einmal erstellen und wiederverwenden (effizienter)
        self.ocean = mss.mss()

        # Thread-safe Debug-State für DebugOverlay (debugtools.py)
        # Lock stellt sicher dass Main-Thread und Bot-Thread nicht gleichzeitig schreiben/lesen
        self._debug_lock = threading.Lock()
        self._debug_state = {
            "scan_frame":   None,  # Letzter SCAN_WATERS Screenshot
            "ripple_frame": None,  # Letzter tide_zone Screenshot
            "buoy":         None,  # Letzte erkannte Buoy-Position
        }

    @property
    def debug_state(self) -> dict:
        """
        Thread-safe Lesezugriff auf den Debug-State.
        Gibt eine Kopie zurück damit der Main-Thread nicht mit veralteten
        Referenzen arbeitet während der Bot-Thread schreibt.
        """
        with self._debug_lock:
            return dict(self._debug_state)

    def _update_debug(self, **kwargs):
        """
        Thread-safe Schreibzugriff auf den Debug-State.
        Wird vom Bot-Thread aufgerufen.

        Args:
            **kwargs: Beliebige debug_state keys mit neuen Werten
        """
        with self._debug_lock:
            self._debug_state.update(kwargs)

    def _grab_waters(self, region: tuple | None = None) -> np.ndarray:
        """
        Macht einen Screenshot des Bildschirms oder einer bestimmten Region.

        Args:
            region: (x, y, width, height) oder None für Vollbild

        Returns:
            Screenshot als BGR-Array (OpenCV-Format)
        """
        if region:
            x, y, w, h = region
            swell = {"top": y, "left": x, "width": w, "height": h}
        else:
            swell = self.ocean.monitors[1]  # Primärer Monitor

        snapshot = self.ocean.grab(swell)
        # mss liefert BGRA, OpenCV braucht BGR → Alpha-Kanal entfernen
        return cv2.cvtColor(np.array(snapshot), cv2.COLOR_BGRA2BGR)

    def _mask_red_shore(self, hsv_frame: np.ndarray) -> np.ndarray:
        """
        Erstellt eine binäre Maske aller roten Pixel im Bild.

        Rot liegt im HSV-Farbraum an zwei Stellen (Hue nahe 0° und nahe 180°),
        daher werden zwei Masken erstellt und kombiniert.

        Args:
            hsv_frame: Bild im HSV-Farbraum

        Returns:
            Binäre Maske (255 = roter Pixel, 0 = kein roter Pixel)
        """
        low1  = np.array(self.config.SHORE_HUE_LOW_1)
        high1 = np.array(self.config.SHORE_HUE_HIGH_1)
        low2  = np.array(self.config.SHORE_HUE_LOW_2)
        high2 = np.array(self.config.SHORE_HUE_HIGH_2)

        swell1 = cv2.inRange(hsv_frame, low1, high1)
        swell2 = cv2.inRange(hsv_frame, low2, high2)

        # Beide Masken kombinieren (OR)
        return cv2.bitwise_or(swell1, swell2)

    def find_buoy(self) -> tuple | None:
        """
        Sucht den Angelbobber (roter Federkiel) auf dem Bildschirm.

        Ablauf:
            1. Screenshot machen
            2. In HSV konvertieren
            3. Rote Pixel maskieren
            4. Zusammenhängende Bereiche (Contours) finden
            5. Wahrscheinlichsten Buoy-Kandidaten zurückgeben

        Schreibt scan_frame und buoy in debug_state.

        Returns:
            (x, y) absolute Bildschirmkoordinaten des Buoys, oder None
        """
        frame = self._grab_waters(self.config.SCAN_WATERS)

        # Frame für DebugOverlay speichern
        self._update_debug(scan_frame=frame.copy(), buoy=None)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        shore_mask = self._mask_red_shore(hsv)

        # Morphologische Operation: kleine Lücken schließen, Rauschen entfernen
        kernel = np.ones((3, 3), np.uint8)
        shore_mask = cv2.morphologyEx(shore_mask, cv2.MORPH_CLOSE, kernel)
        shore_mask = cv2.morphologyEx(shore_mask, cv2.MORPH_OPEN, kernel)

        swells, _ = cv2.findContours(
            shore_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not swells:
            return None

        # Kandidaten nach Größe filtern
        calm_swells = [
            s for s in swells
            if self.config.MIN_BUOY_DRIFT < cv2.contourArea(s) < self.config.MAX_BUOY_DRIFT
        ]

        if not calm_swells:
            return None

        buoy_swell = max(calm_swells, key=cv2.contourArea)

        M = cv2.moments(buoy_swell)
        if M["m00"] == 0:
            return None

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # Offset addieren falls SCAN_WATERS gesetzt ist
        if self.config.SCAN_WATERS:
            ox, oy, _, _ = self.config.SCAN_WATERS
            cx += ox
            cy += oy

        buoy = (cx, cy)

        # Buoy-Position in debug_state speichern
        self._update_debug(buoy=buoy)

        return buoy

    def await_ripple(self, buoy: tuple) -> bool:
        """
        Überwacht den Buoy auf eine Ripple (Splash-Animation = Biss).

        Funktioniert durch Frame-Differenz:
            - Nimmt regelmäßig Screenshots der Buoy-Region (tide_zone)
            - Vergleicht aktuellen Frame mit dem vorherigen
            - Starke Veränderung = Wassersplash = Biss

        Schreibt ripple_frame laufend in debug_state.

        Args:
            buoy: (x, y) Bildschirmkoordinaten des Buoys

        Returns:
            True wenn Ripple (Biss) erkannt, False bei Timeout
        """
        bx, by = buoy
        radius = self.config.RIPPLE_RADIUS

        tide_zone = (bx - radius, by - radius, radius * 2, radius * 2)

        prev_wave = None
        drift_start = time.time()

        while time.time() - drift_start < self.config.MAX_DRIFT_TIME:
            current_wave = self._grab_waters(tide_zone)

            # Frame für DebugOverlay speichern
            self._update_debug(ripple_frame=current_wave.copy())

            gray_wave = cv2.cvtColor(current_wave, cv2.COLOR_BGR2GRAY)
            gray_wave = cv2.GaussianBlur(gray_wave, (5, 5), 0)

            if prev_wave is not None:
                delta = cv2.absdiff(prev_wave, gray_wave)

                _, swell_thresh = cv2.threshold(
                    delta,
                    self.config.RIPPLE_THRESHOLD,
                    255,
                    cv2.THRESH_BINARY
                )

                swell_area = cv2.countNonZero(swell_thresh)

                if swell_area > self.config.RIPPLE_MIN_SWELL:
                    self.log.debug(f"Ripple area: {swell_area}px")
                    return True

            prev_wave = gray_wave
            time.sleep(self.config.TIDE_PULSE)

        return False

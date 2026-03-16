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
================================================================================
"""

import time
import logging

import cv2
import numpy as np
import mss

from tideconfig import TideConfig


class ShoreWatch:
    """
    Beobachtet den Bildschirm: findet den Buoy (Bobber) und erkennt Ripples (Bisse).
    """

    def __init__(self, config: TideConfig):
        self.config = config
        self.log = logging.getLogger(__name__)
        # mss-Instanz einmal erstellen und wiederverwenden (effizienter)
        self.ocean = mss.mss()

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

        Returns:
            (x, y) absolute Bildschirmkoordinaten des Buoys, oder None
        """
        frame = self._grab_waters(self.config.SCAN_WATERS)
        hsv   = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        shore_mask = self._mask_red_shore(hsv)

        # Morphologische Operation: kleine Lücken schließen, Rauschen entfernen
        kernel = np.ones((3, 3), np.uint8)
        shore_mask = cv2.morphologyEx(shore_mask, cv2.MORPH_CLOSE, kernel)
        shore_mask = cv2.morphologyEx(shore_mask, cv2.MORPH_OPEN, kernel)

        # Zusammenhängende rote Bereiche finden
        swells, _ = cv2.findContours(
            shore_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not swells:
            return None

        # Kandidaten nach Größe filtern (zu klein = Rauschen, zu groß = UI-Element)
        calm_swells = [
            s for s in swells
            if self.config.MIN_BUOY_DRIFT < cv2.contourArea(s) < self.config.MAX_BUOY_DRIFT
        ]

        if not calm_swells:
            return None

        # Größten validen Bereich als Buoy wählen
        buoy_swell = max(calm_swells, key=cv2.contourArea)

        # Mittelpunkt des Buoys berechnen
        M = cv2.moments(buoy_swell)
        if M["m00"] == 0:
            return None

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # Falls SCAN_WATERS gesetzt ist: Offset addieren für absolute Koordinaten
        if self.config.SCAN_WATERS:
            ox, oy, _, _ = self.config.SCAN_WATERS
            cx += ox
            cy += oy

        return (cx, cy)

    def await_ripple(self, buoy: tuple) -> bool:
        """
        Überwacht den Buoy auf eine Ripple (Splash-Animation = Biss).

        Funktioniert durch Frame-Differenz:
            - Nimmt regelmäßig Screenshots der Buoy-Region
            - Vergleicht aktuellen Frame mit dem vorherigen
            - Starke Veränderung = Wassersplash = Biss

        Args:
            buoy: (x, y) Bildschirmkoordinaten des Buoys

        Returns:
            True wenn Ripple (Biss) erkannt, False bei Timeout
        """
        bx, by = buoy
        radius = self.config.RIPPLE_RADIUS

        # Überwachungsregion um den Buoy
        tide_zone = (bx - radius, by - radius, radius * 2, radius * 2)

        prev_wave = None
        drift_start = time.time()

        while time.time() - drift_start < self.config.MAX_DRIFT_TIME:
            current_wave = self._grab_waters(tide_zone)
            gray_wave = cv2.cvtColor(current_wave, cv2.COLOR_BGR2GRAY)
            # Leichtes Blur reduziert Fehlalarme durch Bildrauschen
            gray_wave = cv2.GaussianBlur(gray_wave, (5, 5), 0)

            if prev_wave is not None:
                # Differenz zwischen aktuellem und vorherigem Frame
                delta = cv2.absdiff(prev_wave, gray_wave)

                # Nur signifikante Veränderungen zählen
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

        # Timeout – kein Biss innerhalb der Wartezeit
        return False

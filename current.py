"""
================================================================================
Current - SafeHaven Input Controller
================================================================================

Dieses Modul steuert alle Tastatur- und Mauseingaben.
Es hält die einzige Instanz von Drift (human behavior engine).

WICHTIG – Drift-Singleton:
    Current erstellt Drift einmalig als self.drift.
    Alle anderen Module (safehaven.py, harbor.py) greifen über
    current.drift auf diese Instanz zu – niemals eine eigene Drift-Instanz
    erstellen, sonst hat man zwei unabhängige _casts_since_break Zähler.

    Richtig:   human = current.drift
    Falsch:    human = Drift(config)   ← zweite Instanz, Break-Zähler kaputt

Ablauf bei reel_in():
    1. Drift entscheidet ob Fehlklick passiert
    2. Natürliche Reaktionsverzögerung abwarten
    3. Maus mit variabler Geschwindigkeit bewegen
    4. Mit oder ohne Offset klicken
================================================================================
"""

import time
import random
import logging

import pyautogui

from tideconfig import TideConfig
from drift import Drift


class Current:
    """
    Steuert Tastatur- und Mauseingaben.
    Hält die einzige Drift-Instanz des gesamten Projekts.
    """

    def __init__(self, config: TideConfig):
        self.config = config
        self.log = logging.getLogger(__name__)

        # Einzige Drift-Instanz – von außen über current.drift zugreifbar
        self.drift = Drift(config)

        # Leichte natürliche Verzögerung zwischen pyautogui-Aktionen
        pyautogui.PAUSE = 0.05

    def cast(self):
        """
        Wirft die Angel aus.

        Ablauf:
            1. Prüft ob eine AFK-Pause fällig ist (sehr selten)
            2. Wartet eine natürliche Pre-Cast Pause
            3. Drückt CAST_KEY
            4. Erhöht den Drift-Wurf-Zähler
        """
        # AFK-Pause prüfen – erst nach mind. 3 Würfen möglich
        if self.drift.should_take_micro_break():
            self.drift.take_micro_break()

        # Natürliche Pause vor dem Auswerfen (variiert je nach Konzentration)
        time.sleep(self.drift.pre_cast_pause())

        pyautogui.press(self.config.CAST_KEY)
        self.drift.increment_cast_counter()
        self.log.debug(f"Cast key pressed: '{self.config.CAST_KEY}'")

    def reel_in(self, buoy: tuple) -> bool:
        """
        Holt die Angel ein – Rechtsklick auf den Buoy.

        Beinhaltet menschliche Unvollkommenheiten via Drift:
            - Variable Reaktionszeit vor dem Klick
            - Seltener Fehlklick (~2%) mit anschließender Verwirrungs-Pause
            - Variable Mausgeschwindigkeit (±30%)

        Args:
            buoy: (x, y) absolute Bildschirmkoordinaten des Buoys

        Returns:
            True  = Buoy erfolgreich angeklickt
            False = Fehlklick (danebengeklickt), neuer Wurf nötig
        """
        bx, by = buoy

        # 1. Menschliche Reaktionsverzögerung abwarten
        time.sleep(self.drift.natural_reaction_delay())

        # 2. Fehlklick? (sehr selten, ~2%)
        if self.drift.should_miss_click():
            self.log.info("Missed the bobber! (human error)")
            ox, oy = self.drift.miss_click_offset()

            pyautogui.moveTo(bx + ox, by + oy, duration=self.drift.natural_mouse_speed())
            time.sleep(random.uniform(0.04, 0.08))
            pyautogui.click(button="right")

            self.drift.recover_after_miss()
            return False

        # 3. Normaler Klick mit leichtem Zufalls-Offset
        wobble = self.config.CAST_WOBBLE
        aim_x = bx + random.randint(-wobble, wobble)
        aim_y = by + random.randint(-wobble, wobble)

        pyautogui.moveTo(aim_x, aim_y, duration=self.drift.natural_mouse_speed())
        time.sleep(random.uniform(0.04, 0.09))
        pyautogui.click(button="right")

        self.log.debug(f"Reeled in at: ({aim_x}, {aim_y})")
        return True

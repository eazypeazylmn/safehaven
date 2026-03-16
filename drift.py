"""
================================================================================
Drift - SafeHaven Human Behavior Engine
================================================================================

Dieses Modul simuliert menschliches, unvollkommenes Verhalten beim Angeln.
Kein Mensch ist perfekt – und genau das macht diesen Bot realistisch.

Implementierte Verhaltensweisen:
    - Zufällige Pausen zwischen Aktionen (Reaktionszeit variiert)
    - Gelegentliches Danebenkliccken beim Einholen (sehr selten, ~2%)
    - Kurze AFK-Pausen (ab und zu schaut man halt weg vom Bildschirm)
    - Leicht variable Mausgeschwindigkeit (nicht immer gleich schnell)
    - Gelegentliches "zu früh" oder "zu spät" reagieren auf einen Biss

Alle Wahrscheinlichkeiten sind in tideconfig.py konfigurierbar.

Technische Anmerkung:
    Alle Zufallsentscheidungen basieren auf random.random() (0.0–1.0).
    Ein Wert von 0.02 bedeutet 2% Wahrscheinlichkeit pro Aufruf.

Wichtig:
    Drift wird einmal in Current instanziiert und von dort weitergereicht.
    Niemals eine zweite Drift-Instanz erstellen – sonst hat man zwei
    unabhängige _casts_since_break Zähler und das Break-System funktioniert nicht.
================================================================================
"""

import time
import random
import logging

from tideconfig import TideConfig


class Drift:
    """
    Human Behavior Engine für SafeHaven.
    Wird einmal in Current() erstellt und als current.drift weitergereicht.
    """

    def __init__(self, config: TideConfig):
        self.config = config
        self.log = logging.getLogger(__name__)

        # Interner Zähler – Breaks sind erst nach mehreren Würfen am Stück möglich
        self._casts_since_break = 0

    # -------------------------------------------------------------------------
    # Reaction timing
    # -------------------------------------------------------------------------

    def natural_reaction_delay(self) -> float:
        """
        Simuliert menschliche Reaktionszeit nach einem erkannten Biss.

        Menschen reagieren nicht sofort – es gibt immer eine kurze Verzögerung
        zwischen "Biss sehen" und "Maus bewegen". Dazu kommt leichte Varianz.

        Returns:
            Wartezeit in Sekunden bevor die Maus bewegt wird
        """
        base = self.config.REACTION_BASE_DELAY

        # Gelegentlich etwas langsamer reagieren (man schaut kurz woanders hin)
        if random.random() < self.config.SLOW_REACTION_CHANCE:
            delay = base + random.uniform(0.3, 0.9)
            self.log.debug(f"Slow reaction: {delay:.2f}s")
        else:
            # Normale Reaktion: Basis ± kleine Varianz
            delay = base + random.uniform(-0.05, 0.2)

        return max(0.05, delay)  # Minimum 50ms

    def pre_cast_pause(self) -> float:
        """
        Pause vor dem Auswerfen der Angel.

        Variiert je nachdem ob man gerade "konzentriert" ist oder kurz wartet.

        Returns:
            Wartezeit in Sekunden
        """
        # Manchmal kurz zögern bevor man wirft (15% Chance)
        if random.random() < 0.15:
            return random.uniform(0.4, 1.2)
        return random.uniform(0.05, 0.25)

    # -------------------------------------------------------------------------
    # Miss click (danebengeklickt)
    # -------------------------------------------------------------------------

    def should_miss_click(self) -> bool:
        """
        Entscheidet ob beim Einholen danebengeklickt wird.

        Sehr seltenes Ereignis (~2% Chance). Passiert echten Spielern wenn
        der Bobber sich bewegt hat oder man kurz unkonzentriert war.

        Returns:
            True = danebenkliccken, False = normal klicken
        """
        return random.random() < self.config.MISS_CLICK_CHANCE

    def miss_click_offset(self) -> tuple:
        """
        Berechnet wie weit daneben geklickt wird.

        Der Klick geht in eine zufällige Richtung leicht am Buoy vorbei –
        nah genug um realistisch zu wirken, weit genug um zu verfehlen.

        Returns:
            (offset_x, offset_y) in Pixeln
        """
        distance = random.randint(15, 35)
        offset_x = random.choice([-1, 1]) * random.randint(10, distance)
        offset_y = random.choice([-1, 1]) * random.randint(5, distance)
        return (offset_x, offset_y)

    def recover_after_miss(self):
        """
        Simuliert die kurze Verwirrung nach einem Fehlklick.
        Kurze Pause (200–600ms) bevor der nächste Wurf startet.
        """
        pause = random.uniform(0.2, 0.6)
        self.log.debug(f"Miss recovery pause: {pause:.2f}s")
        time.sleep(pause)

    # -------------------------------------------------------------------------
    # AFK / Break behavior
    # -------------------------------------------------------------------------

    def should_take_micro_break(self) -> bool:
        """
        Entscheidet ob eine kurze AFK-Pause eingelegt wird.

        Passiert selten (~1.5% pro Wurf). Erst nach mindestens 3 Würfen
        ohne Pause möglich (kein Break direkt beim ersten Wurf).

        Returns:
            True = Pause einlegen
        """
        if self._casts_since_break < 3:
            return False
        return random.random() < self.config.MICRO_BREAK_CHANCE

    def take_micro_break(self):
        """
        Legt eine kurze AFK-Pause ein.
        Dauer: BREAK_MIN_DURATION bis BREAK_MAX_DURATION Sekunden (siehe tideconfig.py).
        Setzt _casts_since_break danach auf 0 zurück.
        """
        duration = random.uniform(
            self.config.BREAK_MIN_DURATION,
            self.config.BREAK_MAX_DURATION
        )
        self.log.info(f"Taking a short break ({duration:.0f}s)...")
        time.sleep(duration)
        self._casts_since_break = 0
        self.log.info("Back at the shore.")

    def increment_cast_counter(self):
        """Zählt Würfe seit der letzten Pause hoch. Wird von Current.cast() aufgerufen."""
        self._casts_since_break += 1

    # -------------------------------------------------------------------------
    # Mouse speed variation
    # -------------------------------------------------------------------------

    def natural_mouse_speed(self) -> float:
        """
        Gibt eine leicht variierte Mausgeschwindigkeit zurück.

        Kein Mensch bewegt die Maus immer gleich schnell.
        Variiert DRIFT_SPEED aus tideconfig.py um ±30%.

        Returns:
            Mausbewegungszeit in Sekunden (minimum 0.05s)
        """
        base = self.config.DRIFT_SPEED
        variation = base * random.uniform(-0.3, 0.3)
        return max(0.05, base + variation)

    # -------------------------------------------------------------------------
    # Early / late reaction
    # -------------------------------------------------------------------------

    def should_react_early(self) -> bool:
        """
        Prüft ob zu früh auf einen vermeintlichen Biss reagiert wird.

        Sehr selten (~1%) – man glaubt einen Biss gesehen zu haben
        obwohl es nur Wasserbewegung war.

        Returns:
            True = zu früh einziehen (falscher Alarm)
        """
        return random.random() < self.config.EARLY_REACTION_CHANCE

    def should_react_late(self) -> bool:
        """
        Prüft ob zu spät auf einen echten Biss reagiert wird.

        Selten (~3%) – man war kurz abgelenkt, reagiert mit
        zusätzlicher Verzögerung. Kann dazu führen dass der Fisch entwischt.

        Returns:
            True = zusätzliche Verzögerung vor dem Einholen
        """
        return random.random() < self.config.LATE_REACTION_CHANCE

    def late_reaction_delay(self) -> float:
        """
        Zusätzliche Verzögerung bei später Reaktion (0.3–1.1 Sekunden).

        Returns:
            Zusätzliche Wartezeit in Sekunden
        """
        return random.uniform(0.3, 1.1)

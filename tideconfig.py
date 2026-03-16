"""
================================================================================
TideConfig - SafeHaven Configuration
================================================================================

Hier werden ALLE einstellbaren Parameter des Bots zentral verwaltet.
Passe diese Werte an dein System und deine WoW-Einstellungen an.

Wichtige Anpassungen vor dem ersten Start:
    - CAST_KEY          Taste auf der die Angelrute liegt
    - SCAN_WATERS       Bildschirmbereich für die Bobber-Suche
                        (None = ganzer Bildschirm, aber langsamer)
================================================================================
"""


class TideConfig:
    """
    Zentrale Konfigurationsklasse. Alle Parameter können hier angepasst werden.
    """

    # -------------------------------------------------------------------------
    # Key bindings
    # -------------------------------------------------------------------------

    # Taste auf der die Angelrute in der WoW Actionbar liegt
    CAST_KEY: str = "1"

    # -------------------------------------------------------------------------
    # Timing (in seconds)
    # -------------------------------------------------------------------------

    # Wartezeit nach dem Auswerfen bis der Bobber im Wasser landet
    SETTLE_DRIFT: float = 1.5

    # Maximale Wartezeit auf einen Biss (WoW Classic: Angel bleibt ~30s im Wasser)
    MAX_DRIFT_TIME: float = 28.0

    # Wartezeit nach dem Looten (für Loot-Animation)
    HAUL_DELAY: float = 0.5

    # Wartezeit zwischen den Frames bei der Bewegungserkennung
    TIDE_PULSE: float = 0.05  # 50ms ≈ 20 FPS Analyse

    # -------------------------------------------------------------------------
    # Screen search region
    # -------------------------------------------------------------------------

    # Bereich des Bildschirms in dem nach dem Bobber gesucht wird.
    # Format: (x_start, y_start, width, height) in Pixeln
    # None = ganzer Bildschirm (langsamer, aber universell)
    #
    # Tipp: Nur den Wasserbereich scannen – schneller und weniger Fehlalarme
    # durch rote UI-Elemente (Healthbars etc.)
    #
    # Beispiel für 1920x1080, untere Bildschirmhälfte:
    # SCAN_WATERS = (0, 400, 1920, 680)
    SCAN_WATERS: tuple | None = None

    # -------------------------------------------------------------------------
    # Buoy color detection (HSV color space)
    # -------------------------------------------------------------------------
    # Der rote Federkiel des Angelbobbers wird per HSV-Farberkennung gefunden.
    # HSV = Hue (Farbton 0-180), Saturation (Sättigung 0-255), Value (Helligkeit 0-255)
    #
    # Rot liegt im HSV-Farbraum an zwei Stellen (Hue nahe 0° und nahe 180°),
    # daher gibt es zwei Farbbereich-Paare die beide geprüft werden.
    #
    # Falls der Bobber nicht erkannt wird:
    #   1. Screenshot vom Bobber machen
    #   2. In GIMP öffnen: Farbe mit Pipette auswählen → HSV-Werte ablesen
    #   3. SHORE_HUE_*-Werte entsprechend anpassen (±15 Toleranz empfohlen)

    # Roter Farbbereich 1 (unteres Rot, Hue 0-10)
    SHORE_HUE_LOW_1: tuple = (0, 120, 70)
    SHORE_HUE_HIGH_1: tuple = (10, 255, 255)

    # Roter Farbbereich 2 (oberes Rot, Hue 170-180)
    SHORE_HUE_LOW_2: tuple = (170, 120, 70)
    SHORE_HUE_HIGH_2: tuple = (180, 255, 255)

    # -------------------------------------------------------------------------
    # Buoy detection filters
    # -------------------------------------------------------------------------

    # Mindestgröße des erkannten roten Bereichs in Pixeln (filtert Bildrauschen)
    MIN_BUOY_DRIFT: int = 50

    # Maximalgröße des erkannten Bereichs (filtert zu große rote Objekte wie UI)
    MAX_BUOY_DRIFT: int = 2000

    # -------------------------------------------------------------------------
    # Ripple detection (splash animation = bite)
    # -------------------------------------------------------------------------

    # Überwachungsbereich um den Bobber (Radius in Pixeln)
    RIPPLE_RADIUS: int = 40

    # Minimale Anzahl Pixel die sich ändern müssen damit ein Biss erkannt wird.
    # Zu niedrig = Fehlalarme durch natürliche Wasserbewegung
    # Zu hoch   = echte Bisse werden verpasst
    RIPPLE_THRESHOLD: int = 15

    # Mindestfläche der erkannten Bewegung in Pixeln
    RIPPLE_MIN_SWELL: int = 30

    # -------------------------------------------------------------------------
    # Mouse movement
    # -------------------------------------------------------------------------

    # Basis-Dauer der Mausbewegung zum Bobber (in Sekunden)
    # Drift.natural_mouse_speed() variiert diesen Wert um ±30%
    DRIFT_SPEED: float = 0.18

    # Zufälliger Pixel-Offset beim Klick (wirkt natürlicher)
    CAST_WOBBLE: int = 3

    # -------------------------------------------------------------------------
    # Human behavior (drift.py)
    # =========================================================================
    # Alle Wahrscheinlichkeiten sind Werte zwischen 0.0 und 1.0
    # Beispiel: 0.02 = 2% Chance pro Aufruf
    # -------------------------------------------------------------------------

    # -- Reaktionszeit --------------------------------------------------------

    # Basis-Reaktionszeit nach erkanntem Biss (in Sekunden)
    REACTION_BASE_DELAY: float = 0.18

    # Chance auf eine längere Reaktionszeit ("kurz abgelenkt")
    SLOW_REACTION_CHANCE: float = 0.08   # 8%

    # -- Fehlklick ------------------------------------------------------------

    # Chance beim Einholen leicht danebenzuklicken
    # Sehr selten halten – ein echter Spieler verfehlt den Bobber kaum
    MISS_CLICK_CHANCE: float = 0.02      # 2%

    # -- AFK / Micro Break ----------------------------------------------------

    # Chance pro Wurf auf eine kurze Pause (schaut auf Handy, trinkt etc.)
    MICRO_BREAK_CHANCE: float = 0.015    # 1.5%

    # Minimale Pausendauer in Sekunden
    BREAK_MIN_DURATION: float = 5.0

    # Maximale Pausendauer in Sekunden
    BREAK_MAX_DURATION: float = 45.0

    # -- Frühe / späte Reaktion -----------------------------------------------

    # Chance zu früh einzuziehen (falscher Alarm – Wasserbewegung verwechselt)
    EARLY_REACTION_CHANCE: float = 0.01  # 1%

    # Chance zu spät auf einen echten Biss zu reagieren
    LATE_REACTION_CHANCE: float = 0.03   # 3%

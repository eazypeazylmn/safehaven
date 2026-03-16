"""
================================================================================
SafeHaven - WoW Classic Fishing Bot (SSC Edition)
================================================================================

Beschreibung:
    Automatisierter Fishing Bot für WoW Classic (privater Server).
    Verwendet OpenCV zur visuellen Erkennung des Angelbobbers auf dem Bildschirm,
    ohne direkten Speicherzugriff (kein Memory Reading).

Funktionsweise:
    1. Wirft die Angel mit der konfigurierten Taste
    2. Sucht den roten Federkiel (Bobber) per Farberkennung auf dem Bildschirm
    3. Überwacht die Bobber-Region auf Bewegung (Splash-Animation)
    4. Reagiert mit menschlicher Unvollkommenheit (Drift-Modul)
    5. Führt Rechtsklick auf den Bobber aus und lootet
    6. Wiederholt den Vorgang

Voraussetzungen:
    - Python 3.9+
    - Abhängigkeiten: siehe requirements.txt
    - WoW Classic auf einem privaten Server
    - Angel muss auf einer Taste liegen (Standard: '1')
    - "Auto Loot" in WoW aktiviert (Interface Options)

Verwendung:
    python safehaven.py        → Bot im Terminal (kein GUI)
    python harbor.py           → Bot mit GUI (empfohlen)
    Doppelklick SafeHaven.bat  → GUI starten per Doppelklick

    Bot stoppen: Maus in obere linke Ecke (pyautogui Failsafe) oder Strg+C

Konfiguration:
    Alle einstellbaren Parameter befinden sich in tideconfig.py

Hinweis zu Drift:
    current.drift ist die einzige Drift-Instanz im gesamten Projekt.
    Nicht noch mal Drift(config) aufrufen – sonst stimmt der Break-Zähler nicht.

Version:    1.1.0 (SSC Edition – Human Behavior Update)
================================================================================
"""

import time
from datetime import datetime

import pyautogui

from tideconfig import TideConfig
from shorewatch import ShoreWatch
from current import Current
from ripple import setup_ripple


def cast_off():
    """
    Hauptschleife des Fishing Bots.
    Cast -> Find Buoy -> Wait for Ripple -> (Human Behavior) -> Loot -> Repeat

    Drift wird über current.drift referenziert (nicht neu instanziiert).
    """
    log = setup_ripple()
    config = TideConfig()
    shore = ShoreWatch(config)
    current = Current(config)
    human = current.drift  # Drift-Singleton aus Current – nicht neu instanziieren!

    log.info("=" * 60)
    log.info("SafeHaven - WoW Classic Fishing Bot (SSC Edition)")
    log.info(f"Fishing key:    '{config.CAST_KEY}'")
    log.info(f"Max drift time: {config.MAX_DRIFT_TIME}s")
    log.info(f"Miss chance:    {config.MISS_CLICK_CHANCE * 100:.1f}%")
    log.info(f"Break chance:   {config.MICRO_BREAK_CHANCE * 100:.1f}% per cast")
    log.info("To stop: move mouse to top-left corner or Ctrl+C")
    log.info("=" * 60)

    # Kurze Pause damit der Spieler ins WoW-Fenster klicken kann
    log.info("Launching in 3 seconds...")
    time.sleep(3)

    session_start = datetime.now()
    wave_count  = 0   # Anzahl Würfe gesamt
    haul_count  = 0   # Erfolgreiche Fänge
    miss_count  = 0   # Fehlklicks (danebengeklickt)
    escape_count = 0  # Fisch entwischt (kein Biss in Zeit)
    early_count = 0   # Zu früh eingezogen (falscher Alarm)
    break_count = 0   # Kurze AFK-Pausen

    try:
        while True:
            wave_count += 1
            log.info(f"--- Wave #{wave_count} ---")

            # 1. Angel auswerfen (inkl. möglicher AFK-Pause in current.cast())
            was_breaking = human._casts_since_break == 0 and wave_count > 1
            current.cast()
            if was_breaking:
                break_count += 1

            log.info("Line cast, scanning the shore...")
            time.sleep(config.SETTLE_DRIFT)

            # 2. Buoy auf dem Bildschirm lokalisieren
            buoy = shore.find_buoy()

            if buoy is None:
                log.warning("Buoy not spotted! Retrying...")
                time.sleep(1)
                continue

            log.info(f"Buoy spotted at: {buoy}")

            # 3. Prüfen ob zu früh reagiert wird (falscher Alarm, ~1%)
            if human.should_react_early():
                early_count += 1
                log.info("Reacted too early – false splash! Recasting.")
                current.reel_in(buoy)
                time.sleep(config.HAUL_DELAY)
                continue

            # 4. Auf echten Biss (Ripple) warten
            log.info("Reading the tide...")
            bite = shore.await_ripple(buoy)

            if not bite:
                escape_count += 1
                log.warning("Fish escaped – no bite in time. Recasting.")
                continue

            log.info("Ripple detected!")

            # 5. Prüfen ob zu spät reagiert wird (~3%)
            if human.should_react_late():
                extra_delay = human.late_reaction_delay()
                log.debug(f"Late reaction (+{extra_delay:.2f}s)")
                time.sleep(extra_delay)

            # 6. Einholen (inkl. möglichem Fehlklick via Drift)
            success = current.reel_in(buoy)

            if not success:
                miss_count += 1
                log.info(f"Missed! Total misses: {miss_count}. Recasting.")
                continue

            haul_count += 1
            log.info(f"Hauled in! Total catch: {haul_count}")
            time.sleep(config.HAUL_DELAY)

    except KeyboardInterrupt:
        pass
    finally:
        # Session-Statistiken ausgeben
        duration = datetime.now() - session_start
        log.info("=" * 60)
        log.info("SafeHaven docked.")
        log.info(f"Time at sea:    {str(duration).split('.')[0]}")
        log.info(f"Total waves:    {wave_count}")
        log.info(f"Total haul:     {haul_count}")
        log.info(f"Escaped:        {escape_count}")
        log.info(f"Misses:         {miss_count}")
        log.info(f"Early reacts:   {early_count}")
        log.info(f"Breaks taken:   {break_count}")
        if wave_count > 0:
            catch_rate = (haul_count / wave_count) * 100
            log.info(f"Catch rate:     {catch_rate:.1f}%")
        log.info("=" * 60)


if __name__ == "__main__":
    # pyautogui Failsafe: Maus in obere linke Ecke stoppt das Skript sofort
    pyautogui.FAILSAFE = True
    cast_off()

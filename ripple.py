"""
================================================================================
Ripple - SafeHaven Logger Setup
================================================================================

Richtet das Logging-System ein.

Logs werden gleichzeitig ausgegeben:
    - Im Terminal (mit Zeitstempel)
    - In eine Datei: logs/safehaven_DATUM.log

So kann man Session-Logs nachlesen um z.B. zu sehen
wann der Bot wie viele Fische gefangen hat.
================================================================================
"""

import logging
import os
from datetime import datetime


def setup_ripple(log_level: int = logging.INFO) -> logging.Logger:
    """
    Konfiguriert und gibt den Root-Logger zurück.

    Erstellt automatisch einen 'logs/' Ordner falls er nicht existiert.

    Args:
        log_level: Logging-Level (Standard: INFO)
                   DEBUG zeigt zusätzlich Klick-Details und Ripple-Messwerte

    Returns:
        Konfigurierter Logger
    """
    os.makedirs("logs", exist_ok=True)

    # Log-Dateiname mit aktuellem Datum und Uhrzeit
    tide_mark = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = f"logs/safehaven_{tide_mark}.log"

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Format: [HH:MM:SS] LEVEL - Nachricht
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S"
    )

    # Handler 1: Terminal-Ausgabe
    shore_handler = logging.StreamHandler()
    shore_handler.setFormatter(formatter)
    logger.addHandler(shore_handler)

    # Handler 2: Log-Datei
    tide_handler = logging.FileHandler(log_file, encoding="utf-8")
    tide_handler.setFormatter(formatter)
    logger.addHandler(tide_handler)

    logger.info(f"Tide log: {log_file}")
    return logger

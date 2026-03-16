# SafeHaven 🎣
### WoW Classic Fishing Bot — SSC Edition

Screen-basierter Fishing Bot für WoW Classic (privater Server).
Erkennung via OpenCV – kein Memory Reading, kein Speicherzugriff.

---

## Projektstruktur

```
safehaven/
│
├── SafeHaven.bat     # ▶  Doppelklick → Bot starten (Windows)
│
├── harbor.py         # GUI – Hauptfenster mit Stats & Live-Log (empfohlen)
├── safehaven.py      # Terminal-Modus – Bot ohne GUI
│
├── tideconfig.py     # ⚙️  ALLE Einstellungen zentral hier anpassen
├── shorewatch.py     # Bildschirmerkennung: Buoy finden + Ripple erkennen
├── current.py        # Eingaben: Tastendruck (cast) + Mausklick (reel_in)
│                     #   └─ hält die einzige Drift-Instanz (current.drift)
├── drift.py          # Human Behavior Engine: Fehlklicks, Pausen, Reaktionszeit
├── ripple.py         # Logging: Terminal + Datei unter logs/
│
├── requirements.txt  # Python-Abhängigkeiten
└── logs/             # Automatisch erstellt – Session-Logs
```

---

## Schnellstart

### 1. Python 3.9+ installieren
https://www.python.org/downloads/
→ Wichtig: **"Add Python to PATH"** anhaken beim Installieren!

### 2. Abhängigkeiten installieren
Eingabeaufforderung (cmd) öffnen und ausführen:
```bash
pip install -r requirements.txt
```

### 3. WoW vorbereiten
- Angel auf eine Taste legen (Standard: `1`)
- **Auto Loot aktivieren**: Interface Options → Controls → Auto Loot ✓
- Windowed oder Borderless Windowed Modus empfohlen

### 4. Bot starten
**Doppelklick auf `SafeHaven.bat`** – fertig.

Alternativ manuell:
```bash
python harbor.py      # mit GUI (empfohlen)
python safehaven.py   # nur Terminal
```

---

## Konfiguration (tideconfig.py)

Alle Werte können hier angepasst werden.

### Basis-Einstellungen

| Parameter | Beschreibung | Standard |
|---|---|---|
| `CAST_KEY` | Taste der Angelrute | `"1"` |
| `SCAN_WATERS` | Bildschirmbereich fürs Scannen | `None` (Vollbild) |
| `MAX_DRIFT_TIME` | Max. Wartezeit auf Biss | `28.0s` |
| `SETTLE_DRIFT` | Wartezeit nach dem Wurf | `1.5s` |

### SCAN_WATERS optimieren (empfohlen)
Nur den Wasserbereich scannen – schneller und weniger Fehlalarme durch rote
UI-Elemente (Healthbars, Nameplates etc.):
```python
# Beispiel 1920x1080, untere Bildschirmhälfte:
SCAN_WATERS = (0, 400, 1920, 680)
```

### Human Behavior (drift.py)

| Parameter | Beschreibung | Standard |
|---|---|---|
| `MISS_CLICK_CHANCE` | Chance auf Fehlklick | `0.02` (2%) |
| `MICRO_BREAK_CHANCE` | Chance auf kurze AFK-Pause | `0.015` (1.5%) |
| `BREAK_MIN_DURATION` | Kürzeste Pause | `5s` |
| `BREAK_MAX_DURATION` | Längste Pause | `45s` |
| `EARLY_REACTION_CHANCE` | Zu früh einziehen | `0.01` (1%) |
| `LATE_REACTION_CHANCE` | Zu spät reagieren | `0.03` (3%) |
| `SLOW_REACTION_CHANCE` | Langsame Reaktion | `0.08` (8%) |

---

## Troubleshooting

### Buoy wird nicht gefunden
1. Screenshot vom Bobber machen
2. In GIMP öffnen → Pipette auf den roten Federkiel → HSV-Werte ablesen
3. In `tideconfig.py` unter `SHORE_HUE_*` eintragen (±15 Toleranz)
4. `SCAN_WATERS` auf den Wasserbereich eingrenzen

### Zu viele Fehlalarme (Biss ohne echten Biss)
- `RIPPLE_THRESHOLD` erhöhen (z.B. 15 → 25)
- `RIPPLE_MIN_SWELL` erhöhen (z.B. 30 → 60)

### Bisse werden verpasst
- `RIPPLE_THRESHOLD` verringern (z.B. 15 → 8)
- `RIPPLE_RADIUS` erhöhen (größerer Überwachungsbereich)

---

## Architektur & Wichtige Designentscheidungen

### Drift-Singleton
`Drift` wird **einmal** in `Current.__init__()` erstellt und als `current.drift`
weitergereicht. Niemals eine zweite `Drift(config)` Instanz erstellen – sonst
gibt es zwei unabhängige `_casts_since_break` Zähler und das Break-System
funktioniert nicht korrekt.

```python
# Richtig:
current = Current(config)
human = current.drift

# Falsch:
human = Drift(config)   # zweite Instanz – Break-Zähler stimmt nicht!
```

### Bot → GUI Kommunikation
Der Bot-Thread schreibt nie direkt in tkinter-Widgets (nicht thread-safe).
Stattdessen läuft alles über `update_queue`:

```
Bot-Thread  →  update_queue.put(("log", msg, tag))  →  Main-Thread (_poll_queue)
```

### Screen-Based Detection
Kein Memory Reading. Der Bot nutzt nur:
- `mss` für schnelle Screenshots
- OpenCV HSV-Farberkennung für den Buoy
- Frame-Differenz für die Ripple (Splash-Animation = Biss)

---

## Technischer Ablauf

```
_grab_waters()     Screenshot via mss
      ↓
BGR → HSV          OpenCV Konvertierung
      ↓
_mask_red_shore()  Zwei HSV-Bereiche für Rot kombiniert
      ↓
find_buoy()        Größter roter Bereich = Buoy-Position
      ↓
await_ripple()     Frame-Differenz in Buoy-Region überwachen
      ↓
reel_in()          Rechtsklick auf Buoy (inkl. Drift-Verhalten)
```

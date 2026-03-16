# SafeHaven – Build Guide
### SafeHaven.exe erstellen mit PyInstaller

---

## Voraussetzungen

```bash
pip install -r requirements.txt
pip install pyinstaller
```

---

## Build ausführen

Im Projektordner:
```bash
pyinstaller SafeHaven.spec
```

Die fertige `.exe` liegt danach unter:
```
dist/SafeHaven.exe
```

Einfach per Doppelklick starten – kein Python nötig.

---

## Hinweise

- Build-Dauer: ~1-2 Minuten (OpenCV ist groß)
- Dateigröße: ca. 80-120 MB (normal für gebündelte Python-Apps)
- Windows Defender kann beim ersten Start nachfragen – das ist normal
  (unsigned executable). Einfach "Trotzdem ausführen" klicken.
- Die `logs/` Ordner wird neben der `.exe` automatisch erstellt

## Troubleshooting

**`ModuleNotFoundError` beim Starten der .exe:**
```bash
# hiddenimports in SafeHaven.spec ergänzen, dann neu builden
pyinstaller SafeHaven.spec
```

**Build schlägt fehl mit OpenCV-Fehler:**
```bash
pip install opencv-python-headless
pyinstaller SafeHaven.spec
```

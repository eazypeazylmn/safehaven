@echo off
title SafeHaven - WoW Classic Fishing Bot
cd /d %~dp0
python harbor.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python nicht gefunden oder ein Fehler ist aufgetreten.
    echo Stelle sicher dass Python 3.9+ installiert ist.
    pause
)

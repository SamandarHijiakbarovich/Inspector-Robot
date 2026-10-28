@echo off
rem Inspektor robot oynasini ochadi (PowerShell shart emas).
rem Agar .venv yo'q bo'lsa, avval Ornatish.bat ni ishga tushiring.
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo .venv topilmadi. Avval "Ornatish.bat" ni ishga tushiring.
    pause
    exit /b 1
)

rem pythonw - konsolsiz, faqat oyna ochiladi
start "" ".venv\Scripts\pythonw.exe" main.py gui

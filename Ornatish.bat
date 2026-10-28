@echo off
chcp 65001 >nul
rem Birinchi o'rnatish: .venv yaratadi, kutubxonalarni va brauzerni o'rnatadi.
cd /d "%~dp0"

echo ============================================================
echo   Inspektor robot - o'rnatish
echo ============================================================
echo.

where powershell >nul 2>nul
if errorlevel 1 (
    echo PowerShell topilmadi. Windows 10/11 kerak.
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
    echo.
    echo O'rnatishda xatolik yuz berdi. Yuqoridagi xabarni o'qing.
    pause
    exit /b 1
)

echo.
echo O'rnatish tugadi. Endi "Robot.bat" ni ishga tushiring.
echo Ish stolida yorliq yaratish uchun "Yorliq-yaratish.bat" ni bosing.
pause

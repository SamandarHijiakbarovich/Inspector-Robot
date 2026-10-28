@echo off
rem Ish stolida "Inspektor robot" yorlig'ini yaratadi.
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $lnk = $ws.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Inspektor robot.lnk')); $lnk.TargetPath = (Join-Path '%~dp0' 'Robot.bat'); $lnk.WorkingDirectory = '%~dp0'; $lnk.IconLocation = 'shell32.dll,167'; $lnk.Description = 'Inspektor hisobotlarini avtomatik tekshirish'; $lnk.Save(); Write-Host 'Yorliq yaratildi: ish stolida Inspektor robot'"
pause

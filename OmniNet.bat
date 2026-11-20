@echo off
title OmniNet AI Agent Pro - Lanzador 1-Clic
cd /d "%~dp0"

if "%~1"=="--admin" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList 'main.py serve --live-autorepair' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b 0
)

if "%~1"=="--tray" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'pythonw' -ArgumentList 'main.py tray --live-autorepair' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b 0
)

echo Iniciando OmniNet AI Agent Pro en http://127.0.0.1:8877 ...
python main.py serve
pause

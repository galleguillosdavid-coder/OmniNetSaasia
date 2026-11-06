@echo off
setlocal enabledelayedexpansion
title OmniNet — Cuidador de tu Internet y tu PC

if exist "%~dp0dist\OmniNet.exe" (
    start "" "%~dp0dist\OmniNet.exe"
    exit /b
)

if exist "%~dp0OmniNet.exe" (
    start "" "%~dp0OmniNet.exe"
    exit /b
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python "%~dp0main.py"
    exit /b
)

echo [ERROR] No se encontro OmniNet.exe ni Python.
pause

@echo off
setlocal enabledelayedexpansion
title DRISHTI-V Surveillance System
cd /d "%~dp0"

echo.
echo ======================================================================
echo                 DRISHTI-V UNIFIED LAUNCHER
echo ======================================================================
echo [INFO] Starting DRISHTI-V full software stack in a single terminal...
echo.

:: 1. Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.11+ and add it to your PATH.
    echo.
    pause
    exit /b 1
)

:: 2. Check Node.js / npm
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm was not found in PATH!
    echo Please install Node.js 18+ and add it to your PATH.
    echo.
    pause
    exit /b 1
)

:: 3. Select Python Interpreter (.venv preferred)
if exist "backend\.venv\Scripts\python.exe" (
    set "PY_EXE=backend\.venv\Scripts\python.exe"
    echo [OK] Using virtual environment: backend\.venv
) else (
    set "PY_EXE=python"
    echo [OK] Using system Python
)

:: 4. Check Frontend dependencies
if not exist "frontend\node_modules\" (
    echo [SETUP] Installing frontend npm packages...
    cd /d "%~dp0frontend"
    call npm install
    cd /d "%~dp0"
)

:: 5. Launch Unified Runner (Backend + Frontend + Port Forwarder + Public Tunnel)
echo [OK] Launching all services with live port forwarding...
echo.
set PYTHONUNBUFFERED=1
"%PY_EXE%" -u scripts\run_all.py %*

if %errorlevel% neq 0 (
    echo.
    echo [DRISHTI-V] Process ended with exit code %errorlevel%.
    pause
)

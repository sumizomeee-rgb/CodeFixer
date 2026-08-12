@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title CodeFixer

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart.ps1"
set "CODEFIXER_EXIT=%ERRORLEVEL%"

if not "%CODEFIXER_EXIT%"=="0" (
  echo.
  echo [CodeFixer] Exited with code %CODEFIXER_EXIT%.
  pause
)

exit /b %CODEFIXER_EXIT%

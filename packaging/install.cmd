@echo off
REM ============================================================================
REM  Installateur du pack SAPFX — enveloppe de install.ps1.
REM  Usage : install.cmd [-WithMcp] [-WithBrowsers]
REM ============================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
    echo.
    echo L'installation a echoue. Voir les messages ci-dessus.
    pause
    exit /b 1
)

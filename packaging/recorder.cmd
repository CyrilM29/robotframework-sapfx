@echo off
REM ============================================================================
REM  Lanceur du SAP GUI Recorder (variante pack de déploiement) — double-clic.
REM  Préfère le Python du venv du pack (.venv\, créé par install.cmd, où pywin32
REM  est installé) ; repli sur le Python du PATH sinon.
REM  Prérequis : install.cmd exécuté, SAP Logon ouvert avec une session active.
REM ============================================================================
setlocal
set "GUI=%~dp0tools\recorder\recorder_gui.py"

if not exist "%GUI%" (
    echo Introuvable : "%GUI%"
    echo Lancez ce script depuis la racine du pack SAPFX.
    pause
    exit /b 1
)

REM pythonw du venv = pas de console derrière la fenêtre.
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%GUI%"
    goto :eof
)
if exist "%~dp0.venv\Scripts\python.exe" (
    start "" "%~dp0.venv\Scripts\python.exe" "%GUI%"
    goto :eof
)

echo venv introuvable (.venv\) — lancez d'abord install.cmd. Repli sur le PATH...
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%GUI%"
    goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
    start "" python "%GUI%"
    goto :eof
)

echo Python introuvable dans le PATH. Executez install.cmd d'abord.
pause
endlocal

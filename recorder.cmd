@echo off
REM ============================================================================
REM  Lanceur du SAP GUI Recorder : double-cliquez ce fichier.
REM  Ouvre l'interface visuelle (tools\recorder\recorder_gui.py) d'ou l'on choisit
REM  le mode (dump / capture / survol / record / surlignage) et on lance.
REM  Prerequis : Python installe, SAP Logon ouvert avec une session active.
REM ============================================================================
setlocal
set "GUI=%~dp0tools\recorder\recorder_gui.py"

if not exist "%GUI%" (
    echo Introuvable : "%GUI%"
    echo Lancez ce script depuis la racine du depot sapfx.
    pause
    exit /b 1
)

REM pythonw = pas de console derriere la fenetre ; repli sur python, puis py.
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
where py >nul 2>nul
if %errorlevel%==0 (
    start "" py "%GUI%"
    goto :eof
)

echo Python introuvable dans le PATH. Installez Python ou ajoutez-le au PATH.
pause
endlocal

@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py spiel.py
    if %errorlevel%==0 exit /b 0
)

where python >nul 2>nul
if %errorlevel%==0 (
    python spiel.py
    if %errorlevel%==0 exit /b 0
)

if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" spiel.py
    exit /b %errorlevel%
)

echo Kein Python gefunden. Bitte Python 3 installieren: https://www.python.org/downloads/
pause

@echo off
setlocal
cd /d "%~dp0"

set "PY=.venv-win\Scripts\python.exe"
if exist "%PY%" goto run

set "BOOT="
if exist "%UserProfile%\miniconda3\python.exe" set "BOOT=%UserProfile%\miniconda3\python.exe"
if not defined BOOT if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "BOOT=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined BOOT (
  where py >nul 2>&1
  if not errorlevel 1 set "BOOT=py -3"
)
if not defined BOOT (
  where python >nul 2>&1
  if not errorlevel 1 set "BOOT=python"
)
if not defined BOOT (
  echo [ERROR] Windows Python not found.
  echo Install Python 3 and retry, or create .venv-win first.
  pause
  exit /b 1
)

echo Creating .venv-win ...
%BOOT% -m venv .venv-win
if not exist "%PY%" (
  echo [ERROR] Failed to create .venv-win
  pause
  exit /b 1
)
"%PY%" -m pip install -U pip
"%PY%" -m pip install -r requirements.txt

:run
"%PY%" -c "import yaml,selenium,PyQt6,tzdata" >nul 2>&1
if errorlevel 1 (
  echo Installing requirements ...
  "%PY%" -m pip install -r requirements.txt
)
echo Starting TicketPlus helper with Windows Python...
"%PY%" -m src.main %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%

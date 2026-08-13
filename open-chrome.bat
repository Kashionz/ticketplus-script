@echo off
setlocal
set "PORT=9222"
set "PROFILE=%~dp0.chrome-profile"
set "CHROME="

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME (
  echo [ERROR] Chrome not found.
  pause
  exit /b 1
)

echo Starting Windows Chrome debug port %PORT%
echo Close other Chrome windows first if the port does not bind.
start "" "%CHROME%" --remote-debugging-port=%PORT% --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "https://ticketplus.com.tw/"
echo Login in this Chrome window, then start the helper.
echo Debugger: 127.0.0.1:%PORT%
endlocal

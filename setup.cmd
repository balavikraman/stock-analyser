@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.12+ from python.org and enable "Add Python to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo Setup complete. Edit .env only if you want PostgreSQL/Zerodha now.
echo Run start.cmd to launch Stock Analyzer.
pause

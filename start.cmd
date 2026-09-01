@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First run detected. Running setup...
  call setup.cmd
)
if not exist .env copy .env.example .env >nul
call .venv\Scripts\activate.bat
python run.py

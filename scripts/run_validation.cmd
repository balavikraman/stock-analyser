@echo off
setlocal
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m backend.app.jobs.validation_runner %*
) else (
  python -m backend.app.jobs.validation_runner %*
)

exit /b %ERRORLEVEL%

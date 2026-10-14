@echo off
rem One-time setup: creates .venv, installs packages, downloads the speech model.
cd /d %~dp0
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m mentionalert download-models
echo.
echo Setup done. Optional: install Ollama and run "ollama pull qwen2.5:3b" (see manual.md).
echo Then run run.bat
pause

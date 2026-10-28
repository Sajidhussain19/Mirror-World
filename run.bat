@echo off
REM One-command local run (Windows). Put your keys in .env first (see .env.example).
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo Open http://localhost:8000
uvicorn app.main:app --port 8000

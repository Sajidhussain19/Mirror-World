@echo off
REM One-click local run (Windows): opens VS Code on this folder, then starts Mirror World.
cd /d "%~dp0"
REM (VS Code opened separately)
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set PY="%USERPROFILE%\anaconda3\python.exe"
if not defined PY (echo Python not found. Install from python.org and tick Add to PATH. & pause & exit /b 1)
if not exist .venv %PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
echo.
echo  Mirror World is starting: open http://localhost:8000
echo.
set WATCHFILES_FORCE_POLLING=true
python -m uvicorn app.main:app --port 8000 --reload


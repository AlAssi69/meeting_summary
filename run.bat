@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found at .venv
    echo Create it from this folder:  python -m venv .venv
    echo Then install dependencies:   pip install -r requirements.txt
    exit /b 1
)

call ".venv\Scripts\activate.bat"
py main.py
exit /b %ERRORLEVEL%

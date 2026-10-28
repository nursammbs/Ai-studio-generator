@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Could not create virtual environment. Install Python 3.10+ first.
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
pause

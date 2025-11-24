@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Change working directory to the location of this script
cd /d "%~dp0"

echo [1/3] Creating (or reusing) virtual environment .venv with Python 3.11 ...
py -3.11 -m venv .venv
if errorlevel 1 (
    echo Failed to create virtual environment.
    goto :error
)

rem Activate the virtual environment
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate virtual environment.
    goto :error
)

echo [2/3] Upgrading pip inside the virtual environment ...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/3] Installing project dependencies ...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Starting moblin-smart-translation web server on http://127.0.0.1:5000/settings ...
echo (Press Ctrl+C in this window to stop the server.)
echo.

python app.py --device cpu --quality ultra_low
if errorlevel 1 goto :error

goto :eof

:error
echo.
echo Server failed to start. Please check the messages above.
echo.
pause

endlocal

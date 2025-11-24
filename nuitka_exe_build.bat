@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Change working directory to the location of this script
cd /d "%~dp0"

echo [1/4] Creating (or reusing) virtual environment .venv with Python 3.11 ...
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

echo [2/4] Upgrading pip inside the virtual environment (Python 3.11) ...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/4] Installing project dependencies and Nuitka (Python 3.11) ...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python -m pip install nuitka
if errorlevel 1 goto :error

echo [4/4] Building GUI executable with Nuitka (Python 3.11) ...
python -m nuitka ^
  --onefile ^
  --windows-disable-console ^
  --enable-plugin=tk-inter ^
  gui_app.py
if errorlevel 1 goto :error

echo.
echo Build finished successfully.
echo You should now have gui_app.exe in this folder.
echo.
pause
goto :eof

:error
echo.
echo Build failed. Please check the error messages above.
echo.
pause

endlocal

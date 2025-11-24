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

echo [2/4] Activating virtual environment ...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate virtual environment.
    goto :error
)

echo [3/4] Ensuring dependencies are installed (pip, requirements.txt) ...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [4/4] Checking CUDA support for faster-whisper ...
echo.
python -c "from stt_translate import create_model; print('[check] trying to create CUDA model...'); create_model('cuda'); print('[check] CUDA seems usable for faster-whisper.')"
if errorlevel 1 goto :cuda_error

echo.
echo === CUDA CHECK PASSED ===
echo This machine seems able to run faster-whisper in CUDA (GPU) mode.
echo Try selecting [Device mode = GPU (CUDA)] in the Web UI and start the worker.
echo.
goto :end

:cuda_error
echo.
echo === CUDA CHECK FAILED ===
echo Please review the error messages above.
echo Common causes:
echo   - Missing or incompatible NVIDIA driver
echo   - CUDA Toolkit not installed
echo   - cuDNN (e.g. cudnn_ops64_9.dll) not available on PATH
echo.
echo The app will still run in CPU mode.
echo If you want to use GPU, install CUDA and cuDNN according to the official documentation.
echo.
goto :end

:error
echo.
echo An error occurred during setup. Please review the messages above.
echo.

:end
pause
endlocal

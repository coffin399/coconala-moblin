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
echo このマシンでは faster-whisper を CUDA(GPU) モードで使える可能性があります。
echo Web UI で 動作モード=GPU(CUDA) を選択して試してみてください。
echo.
goto :end

:cuda_error
echo.
echo === CUDA CHECK FAILED ===
echo 上のエラーメッセージを確認してください。
echo 代表的な原因:
echo   - 対応する NVIDIA ドライバが入っていない
echo   - CUDA Toolkit がインストールされていない
echo   - cuDNN (例: cudnn_ops64_9.dll) が PATH に入っていない
echo.
echo このままでもアプリは CPU モードで動作します。
echo GPU を使いたい場合は、公式ドキュメントに従って CUDA / cuDNN をインストールしてください。
echo.
goto :end

:error
echo.
echo セットアップ中にエラーが発生しました。上のメッセージを確認してください。
echo.

:end
pause
endlocal

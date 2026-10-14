@echo off
REM ==============================================================================
REM JobPilot Desktop - Windows Distribution Build Script (v0.1.0-beta.1)
REM ==============================================================================
echo === Building JobPilot Desktop (Windows x64) ===

set VENV_PYTHON=.venv\Scripts\python.exe
if not exist "%VENV_PYTHON%" (
    echo [.venv not found] Creating virtual environment .venv using system Python...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Python is not installed or not in PATH. Please install Python 3.11+.
        exit /b 1
    )
    echo Installing dependencies from requirements.txt...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    "%VENV_PYTHON%" -m pip install -r requirements.txt
)

REM Ensure pyinstaller is installed
"%VENV_PYTHON%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller in virtualenv...
    "%VENV_PYTHON%" -m pip install pyinstaller
)

REM Clean prior build artifacts
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Run PyInstaller build
echo Running PyInstaller build...
"%VENV_PYTHON%" -m PyInstaller --clean --noconfirm JobPilot.spec

if exist "dist\JobPilot" (
    echo Packaging zip distribution...
    for /f "tokens=*" %%i in ('"%VENV_PYTHON%" -c "import app.version; print(app.version.__version__)"') do set APP_VERSION=%%i
    if "%APP_VERSION%"=="" set APP_VERSION=0.1.0-beta.2
    powershell -Command "Compress-Archive -Path dist\JobPilot -DestinationPath dist\JobPilot-v%APP_VERSION%-windows-x64.zip -Force"
    echo === Build Complete! Package created: dist\JobPilot-v%APP_VERSION%-windows-x64.zip ===
) else (
    echo ERROR: Build failed; dist\JobPilot directory was not created.
    exit /b 1
)

@echo off
setlocal
cd /d "%~dp0"

rem Build Sheldon-Paws as ONEDIR: dist\SheldonPaws\SheldonPaws.exe + _internal\
rem For the single-file build use SheldonPaws.spec instead.

set "PY=agent_env\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERROR] %PY% not found.
    echo         Create the venv first:  python -m venv agent_env
    exit /b 1
)

echo Building onedir via SheldonPaws-onedir.spec ...
"%PY%" -m PyInstaller --noconfirm --clean SheldonPaws-onedir.spec
if errorlevel 1 (
    echo [FAIL] Build failed, see PyInstaller messages above.
    exit /b 1
)

echo.
echo [OK] Output folder: dist\SheldonPaws\
echo      Ship the WHOLE folder, not just the exe: dist\SheldonPaws\SheldonPaws.exe
exit /b 0

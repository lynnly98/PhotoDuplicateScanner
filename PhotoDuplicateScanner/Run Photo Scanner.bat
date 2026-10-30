@echo off
setlocal
cd /d "%~dp0"
title Photo Duplicate Scanner
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>&1
if %errorlevel%==0 (
    py -3.14 -c "import sys; assert sys.version_info[:2] == (3,14)" >nul 2>&1
    if not errorlevel 1 goto usepy
)
where python >nul 2>&1
if errorlevel 1 goto no_python
python -c "import sys; assert sys.version_info[:2] == (3,14)" >nul 2>&1
if errorlevel 1 goto no_python
python -m venv --system-site-packages .venv
if errorlevel 1 goto failed
 goto install
:usepy
py -3.14 -m venv --system-site-packages .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -c "import sys,struct; assert sys.version_info[:2] == (3,14) and struct.calcsize('P') == 8"
if errorlevel 1 goto no_python
".venv\Scripts\python.exe" enable_system_packages.py
if errorlevel 1 goto failed
if not exist "data" mkdir "data"
echo Checking installed packages without accessing the internet...
".venv\Scripts\python.exe" -m pip install --no-index --disable-pip-version-check -r requirements.txt > "data\dependency-check.log" 2>&1
if not errorlevel 1 goto run
echo Some required packages are missing or incompatible. Installing them into .venv...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
:run
".venv\Scripts\python.exe" desktop.py
if errorlevel 1 goto failed
exit /b 0
:no_python
echo Python 3.14 (64-bit) was not found. Install it and tick Add Python to PATH.
goto failed
:failed
echo.
echo An error occurred. Please read the message above.
pause
exit /b 1

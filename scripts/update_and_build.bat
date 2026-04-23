@echo off
setlocal
cd /d %~dp0\..

echo [1/5] Sync with GitHub main...
git fetch origin
if errorlevel 1 exit /b 1
git checkout main
if errorlevel 1 exit /b 1
git pull origin main
if errorlevel 1 exit /b 1

echo [2/5] Activate virtual environment...
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate

set PIP_DISABLE_PIP_VERSION_CHECK=1
echo [3/5] Install requirements...
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [4/5] Syntax check...
python -m compileall app
if errorlevel 1 exit /b 1

echo [5/5] Build EXE...
call scripts\build_exe.bat
if errorlevel 1 exit /b 1

echo Done.
exit /b 0

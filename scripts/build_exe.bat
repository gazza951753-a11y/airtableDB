@echo off
setlocal
cd /d %~dp0\..

if not exist .venv (
  py -3.12 -m venv .venv
)

call .venv\Scripts\activate
set PIP_DISABLE_PIP_VERSION_CHECK=1
pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.
  exit /b 1
)

python -m compileall app
if errorlevel 1 (
  echo [ERROR] Syntax check failed. Fix Python errors before build.
  exit /b 1
)

pyinstaller --noconfirm --clean --name AirtableLocalDB --windowed --add-data "app\db\schema.sql;app\db" app\main.py
if errorlevel 1 (
  echo [ERROR] PyInstaller build failed.
  exit /b 1
)

echo EXE assembled: dist\AirtableLocalDB\AirtableLocalDB.exe
exit /b 0

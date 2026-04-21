@echo off
cd /d %~dp0\..
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate
set PIP_DISABLE_PIP_VERSION_CHECK=1
pip install -r requirements.txt
pyinstaller --noconfirm --clean --name AirtableLocalDB --windowed --add-data "app\db\schema.sql;app\db" app\main.py
echo EXE assembled: dist\AirtableLocalDB\AirtableLocalDB.exe

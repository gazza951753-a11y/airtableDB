@echo off
cd /d %~dp0\..
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --name AirtableLocalDB --windowed app\main.py
echo EXE assembled: dist\AirtableLocalDB\AirtableLocalDB.exe

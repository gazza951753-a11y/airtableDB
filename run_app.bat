@echo off
cd /d %~dp0
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate
set PIP_DISABLE_PIP_VERSION_CHECK=1
pip install -r requirements.txt
python -m app.main

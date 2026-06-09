@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
    D:\ADT\Python314\python.exe -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 6080 --reload
pause

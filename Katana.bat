@echo off
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
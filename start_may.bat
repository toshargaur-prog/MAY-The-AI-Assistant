@echo off
title MAY AI Assistant
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\pythonw.exe" "may_assistant.py" %*
) else (
    echo [ERROR] Virtual environment not found in %~dp0.venv
    pause
)

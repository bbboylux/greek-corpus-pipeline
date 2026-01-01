@echo off
title Check the Greek Corpus Pipeline installation
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe CHECK_INSTALL.py
) else (
    echo [ERROR] Cannot find .venv: run setup.bat first.
    pause
)

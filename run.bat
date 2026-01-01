@echo off
title Greek Corpus Pipeline

:: Always work in the folder that holds this file, not in the folder it was
:: launched from: from a shortcut on the desktop the two differ, and without
:: this line the program would look for the .venv of another folder.
cd /d "%~dp0"

:: The environment was created by setup.bat: without it the program cannot start.
if not exist .venv\Scripts\python.exe (
    echo [ERROR] The program has not been installed yet.
    echo.
    echo Double-click setup.bat, wait for it to finish,
    echo then try run.bat again.
    echo.
    pause
    exit /b 1
)

:: pythonw.exe starts the program without a black console window. If the program
:: does not open, remove the "w" below to see the error message.
start "" .venv\Scripts\pythonw.exe app_qt.py

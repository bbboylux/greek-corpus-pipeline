@echo off
setlocal EnableDelayedExpansion
title Greek Corpus Pipeline - Setup

:: Always work in the folder that holds this file, not in the folder it was
:: launched from: from a shortcut the two differ, and without this line the
:: setup would act on the .venv of another folder.
cd /d "%~dp0"

echo ============================================================
echo   Greek Corpus Pipeline - Installation
echo ============================================================
echo.

:: -- Check Python ---------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo.
    echo Download and install Python 3.11 or later from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: during the installation of Python, tick
    echo "Add Python to PATH" before clicking Install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Python found: %PY_VER%

:: Check the minimum version, 3.11
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo [ERROR] Python 3.11 or later is required. Current version: %PY_VER%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 (
    echo [ERROR] Python 3.11 or later is required. Current version: %PY_VER%
    echo Download the latest version from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [1/3] Virtual environment...

:: A .venv that exists is not for that reason an environment that works. It may
:: have been left half-built by an interrupted installation, or created by a
:: Python that is no longer there. Before reusing it we look whether it contains
:: an interpreter, and then whether that interpreter has pip: without pip the
:: next step fails in a way that is hard to understand.
if exist .venv (
    if exist .venv\Scripts\python.exe (
        echo      The environment already exists: checking its state.
    ) else (
        echo [ERROR] The .venv folder exists but does not contain a Python
        echo          interpreter. It is an environment that was left half-built.
        echo.
        echo What to do: delete the .venv folder that sits next to this
        echo file, then double-click setup.bat again.
        echo.
        pause
        exit /b 1
    )
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] The virtual environment could not be created.
        pause
        exit /b 1
    )
)

echo.
echo [2/3] Checking pip...

:: Always "python.exe -m pip", never "pip.exe": the pip.exe script can be missing
:: even when the pip module is there, and when it is missing the message that
:: cmd returns says nothing useful.
.venv\Scripts\python.exe -m pip --version >nul 2>&1
if errorlevel 1 (
    echo      pip does not answer: trying to restore it.
    .venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>&1
    .venv\Scripts\python.exe -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] The virtual environment .venv exists but has no pip, and
        echo          the attempt to restore it did not succeed.
        echo.
        echo Stopping here: continuing with an incomplete environment leads to
        echo an error further on that looks like a problem of the program and is not.
        echo.
        echo What to do, in two steps:
        echo   1. delete the .venv folder that sits next to this file;
        echo   2. double-click setup.bat again.
        echo.
        echo The environment will be recreated from scratch. You lose nothing: .venv
        echo holds only the libraries, not your data or your corpora.
        echo.
        pause
        exit /b 1
    )
    echo      pip restored.
) else (
    echo      pip is present.
)

.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo      [WARNING] pip could not be upgraded. Continuing with
    echo                the version that is present, which works.
)

echo.
echo [3/3] Installing the program...
echo      (pandas, numpy, PyQt6, matplotlib, pyarrow)
echo      This may take a few minutes...
.venv\Scripts\python.exe -m pip install -e . --quiet
if errorlevel 1 (
    echo [ERROR] Installing the dependencies failed.
    echo Check the internet connection and try again.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Greek Corpus Pipeline is installed.
echo ============================================================

:: Stanza and UDPipe are needed only by step 9, "Compare the models", and the
:: program works in full without them. Installing them without asking would mean
:: downloading several hundred megabytes for people who will never use them,
:: while calling them optional. So the setup asks.
echo.
echo Stanza and UDPipe are the two automatic analysers used by step 9,
echo "Compare the models". They are OPTIONAL: the program works in full
echo without them, and the comparison page says so.
echo.
echo Installing them now downloads several hundred megabytes, PyTorch included,
echo and on first use they download their language models, about 60 MB.
echo.
:: The starting value is "n", not empty: "set /p" leaves the variable as it was
:: when Enter is pressed without typing anything, so starting from "n" is what
:: keeps Enter meaning no. Only the first letter is then looked at, so that y,
:: yes and YES all count as yes without having to list them. The two tests sit
:: outside any block in parentheses, where delayed expansion is not needed and
:: cannot surprise.
set "MODELS=n"
set /p "MODELS=Do you want to install them now? (y or yes = yes, enter = no): "
set "CHOICE=n"
if /i "%MODELS:~0,1%"=="y" set "CHOICE=y"
if "%CHOICE%"=="y" (
    echo.
    echo Installing Stanza and UDPipe...
    .venv\Scripts\python.exe -m pip install -e ".[models]" --quiet
    if errorlevel 1 (
        echo.
        echo [WARNING] Installing the models did not succeed.
        echo The program works all the same: step 9 will say that they are not
        echo installed and the buttons that would use them stay disabled.
        echo You can try again later with the command below.
        echo.
        echo   .venv\Scripts\python.exe -m pip install -e ".[models]"
        echo.
    ) else (
        echo Stanza and UDPipe installed.
    )
) else (
    echo.
    echo Skipped. If you later want the comparison with the models, open a
    echo command prompt in this folder and run:
    echo.
    echo   .venv\Scripts\python.exe -m pip install -e ".[models]"
    echo.
)

echo.
echo ============================================================
echo   Installation complete!
echo ============================================================
echo.
echo To start the program, double-click:
echo   run.bat
echo.
echo (You can also create a shortcut to run.bat on the desktop:
echo  right-click run.bat, Send to, Desktop)
echo.
pause

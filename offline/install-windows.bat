@echo off
rem Install terminal-terrarium from this offline bundle (no internet needed).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 install.py %*) else (python install.py %*)
if "%~1"=="" pause

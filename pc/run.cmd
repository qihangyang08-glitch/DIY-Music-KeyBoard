@echo off
setlocal
rem Launch the desktop instrument from any working directory.
cd /d "%~dp0.."
python pc/app/main.py %*
if errorlevel 1 pause

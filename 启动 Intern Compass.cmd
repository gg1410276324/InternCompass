@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "VBS_FILE="

for %%F in ("%ROOT_DIR%*.vbs") do (
    set "VBS_FILE=%%~fF"
)

if defined VBS_FILE (
    start "" wscript.exe "%VBS_FILE%"
    exit /b 0
)

echo Intern Compass no-console launcher was not found.
echo Please double click the .vbs launcher or run:
echo cd /d "%ROOT_DIR%intern_compass"
echo python main.py
pause

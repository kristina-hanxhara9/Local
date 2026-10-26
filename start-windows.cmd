@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Meeting Companion is not installed in this folder. Run .\install-windows.cmd first.
    popd
    exit /b 1
)
".venv\Scripts\python.exe" main.py %*
set "APP_EXIT=%ERRORLEVEL%"
popd
exit /b %APP_EXIT%

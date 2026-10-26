@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1

echo Installing Meeting Companion for Windows 11 x64...
echo Internet is needed for Python packages. Model downloads are approved in the app.
echo.

py -3.12 -c "import platform, struct, sys; ok = sys.platform == 'win32' and sys.getwindowsversion().build >= 26100 and platform.machine().lower() in ('amd64', 'x86_64') and struct.calcsize('P') == 8; print('Windows and Python check:', 'OK' if ok else 'Requires Windows 11 24H2+ x64 and Python 3.12 x64.'); sys.exit(0 if ok else 1)"
if errorlevel 1 goto :failed

py -3.12 -m venv .venv
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" main.py --diagnose
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" main.py --sdk-check
if errorlevel 1 goto :failed

echo.
echo Installation complete. Run .\start-windows.cmd to open Meeting Companion.
echo In Setup, click Download to prepare the local speech model and runtime.
popd
exit /b 0

:failed
echo.
echo Installation stopped. Read the error above and the Troubleshooting section in README.md.
echo Fix the problem and run .\install-windows.cmd again.
popd
exit /b 1

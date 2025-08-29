@echo off
setlocal enableextensions

rem Minimal SimpleScribe launcher (native window via pywebview)
rem - Creates venv if missing
rem - Activates venv
rem - Installs requirements
rem - Runs run_local_server.py (opens native window with taskbar icon)

pushd "%~dp0"

rem Detect Python (prefer py launcher)
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=")
if not defined PY (
  where python >nul 2>&1 && (set "PY=python")
)
if not defined PY (
  echo Python 3 not found in PATH. Please install Python 3 and try again.
  goto :eof
)

rem Create venv if not present
if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv venv || (echo Failed to create virtual environment. & goto :eof)
)

rem Activate venv
call "venv\Scripts\activate" || (echo Failed to activate virtual environment. & goto :eof)

rem Install requirements (quietly)
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt >nul 2>&1

rem Run the local server (opens browser). When it exits, close this window immediately.
python run_local_server.py

popd
endlocal
exit /b 0
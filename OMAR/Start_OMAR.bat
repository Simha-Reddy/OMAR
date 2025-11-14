@echo off
setlocal enableextensions

rem ============================================================================
rem  Start_OMAR.bat (User-facing, double-click this)
rem  Purpose:
rem    - Keep a single obvious launcher for end users
rem    - Run run_local_server.py using the embedded Python interpreter
rem    - Set up the Python environment and path correctly
rem ============================================================================

set "ROOT=%~dp0"
set "PORTABLE_DIR=%ROOT%portable"
set "SRC_DIR=%ROOT%src"
set "RUNTIME_DIR=%ROOT%runtime"
set "PYTHON_EXE=%PORTABLE_DIR%\python\python.exe"
set "SERVER_SCRIPT=%PORTABLE_DIR%\run_server.py"

rem Check if Python executable exists
if not exist "%PYTHON_EXE%" (
  echo [OMAR] ERROR: Python executable not found: %PYTHON_EXE%
  echo         Please ensure the OMAR portable package is complete.
  echo Press any key to close this window...
  pause >nul
  exit /b 1
)

rem Check if server script exists
if not exist "%SERVER_SCRIPT%" (
  echo [OMAR] ERROR: Server script not found: %SERVER_SCRIPT%
  echo         Please ensure the OMAR portable package is complete.
  echo Press any key to close this window...
  pause >nul
  exit /b 1
)

rem Set up Python environment (embedded interpreter in portable\python)
set "PYTHONPATH=%SRC_DIR%;%PYTHONPATH%"
set "PATH=%PORTABLE_DIR%\python;%PORTABLE_DIR%\python\DLLs;%PATH%"
set "OMAR_RUNTIME_ROOT=%RUNTIME_DIR%"
set "OMAR_ENV_FILE=%PORTABLE_DIR%\.env"

rem Change to portable directory (so .env resolves) and run the server
cd /d "%PORTABLE_DIR%"
echo [OMAR] Starting OMAR server...

rem Determine port (default 5050) and auto-open browser to landing page
if "%PORT%"=="" set "PORT=5050"
echo [OMAR] Will open http://127.0.0.1:%PORT%/ in your default browser.
start "OMAR_UI" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:%PORT%/"
"%PYTHON_EXE%" "%SERVER_SCRIPT%" %*

set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo [OMAR] The server exited with error code %EXITCODE%.
  echo Press any key to close this window...
  pause >nul
)
exit /b %EXITCODE%
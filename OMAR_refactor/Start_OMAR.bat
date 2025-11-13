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
set "PYTHON_EXE=%ROOT%\app\python\python.exe"
set "OMAR_DIR=%ROOT%"
set "APP_DIR=%OMAR_DIR%\app"
set "SERVER_SCRIPT=%APP_DIR%\run_server.py"

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

rem Set up Python environment (embedded interpreter in OMAR_refactor\python)
set "PYTHONPATH=%OMAR_DIR%;%APP_DIR%;%PYTHONPATH%"
set "PATH=%ROOT%app\python;%ROOT%OMAR_refactor\app\python\DLLs;%PATH%"

rem Change to OMAR directory and run the server
cd /d "%APP_DIR%"
echo [OMAR] Starting OMAR Refactor server...

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
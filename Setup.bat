@echo off
setlocal enableextensions

rem === SETUP.BAT ===
rem Create venv and install requirements only (no shortcut creation)
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=")
if not defined PY (
  where python >nul 2>&1 && (set "PY=python")
)
if not defined PY (
  echo Python 3 not found in PATH. Please install Python 3 and try again.
  pause
  goto :eof
)

pushd "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv venv || (echo Failed to create virtual environment. & pause & goto :eof)
)

call "venv\Scripts\activate" || (echo Failed to activate virtual environment. & pause & goto :eof)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

popd

:: --- Follow-up instructions ---
set "ICON_PATH=%CD%\static\icon.ico"
set "EXAMPLE_DESKTOP=C:\Users\YOUR_USER_NAME\OneDrive - Department of Veterans Affairs\Desktop"
set "EXAMPLE_APP=%EXAMPLE_DESKTOP%\OMAR\Omar_Simplified_In_Process\Start_OMAR.bat"
set "EXAMPLE_ICON=%EXAMPLE_DESKTOP%\OMAR\Omar_Simplified_In_Process\static\icon.ico"

echo.
echo.
color 0A
echo Setup complete!
echo.
echo To start OMAR:
echo   - Double-click Start_OMAR.bat in this folder.
echo   - Example full path: "%EXAMPLE_APP%"

echo.
echo To create a Desktop shortcut:
echo   1. Right-click Desktop ^> New ^> Shortcut
echo   2. For the location, enter: "%EXAMPLE_APP%"
echo   3. Name it: Start OMAR
echo   4. Right-click the new shortcut ^> Properties ^> Change Icon ^> Browse to: "%EXAMPLE_ICON%"
echo   5. (Optional) Right-click shortcut ^> Pin to taskbar

echo.
color 07
pause

endlocal

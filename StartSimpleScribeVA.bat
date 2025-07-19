REM === SimpleScribeVAStart.BAT ===
@echo off


REM === Clear old session data ===
REM echo Clearing old session data...
REM if exist chunks (
REM     del /q chunks\*.wav >nul 2>&1
REM     del /q chunks\*.txt >nul 2>&1
REM     del /q chunks\*.json >nul 2>&1
REM )


REM === Clear the live transcript file ===
REM if exist live_transcript.txt (
REM     echo. > live_transcript.txt
REM )

REM === Set path to embeddable Python ===
call venv\Scripts\activate


REM === Start the transcribing program in a minimized window ===
REM start /min "" cmd /k python monitor_transcription.py

REM === Start Flask server in a minimized window ===
start /min "" cmd /c python run_local_server.py

REM === Give it a moment to start up ===
timeout /t 15 > nul

REM === Open up in default browser ===
start "" http://127.0.0.1:5000
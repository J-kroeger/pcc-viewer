@echo off
echo Starting PCC-Viewer...

REM Check if running from dist (exe mode) or source (python mode)
if exist "%~dp0PCC-Viewer.exe" (
    start "" "%~dp0PCC-Viewer.exe"
    exit /b
)

REM Fallback: run from Python source
if exist "%~dp0pcc_viewer.py" (
    python "%~dp0pcc_viewer.py"
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to start. Make sure Python 3.8+ is installed.
        echo Install dependencies: pip install -r requirements.txt
        pause
    )
) else (
    echo ERROR: Neither PCC-Viewer.exe nor pcc_viewer.py found.
    echo Please run this from the PCC-Viewer directory.
    pause
)

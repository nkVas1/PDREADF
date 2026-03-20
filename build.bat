@echo off
setlocal
cd /d "%~dp0"

echo Installing project dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Installing PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 goto :error

set "ICON_ARG="
if exist "icon.ico" (
    set "ICON_ARG=--icon=icon.ico"
) else (
    echo [WARN] icon.ico not found. Building without custom icon.
)

echo Building PDREADF...
python -m pyinstaller --clean --onefile --windowed --name PDREADF %ICON_ARG% --collect-all fitz pdreadf.py
if errorlevel 1 goto :error

if not exist "dist\PDREADF.exe" (
    echo [ERROR] Build command finished but dist\PDREADF.exe was not produced.
    goto :error
)

echo.
echo Build complete. Find PDREADF.exe in the dist\ folder.
pause
exit /b 0

:error
echo.
echo [ERROR] Build failed. Check the output above.
pause
exit /b 1

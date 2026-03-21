@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   PDREADF Build Script
echo ============================================
echo.

echo [1/3] Installing project dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python -m pip install pyinstaller
if errorlevel 1 goto :error

echo.
echo [2/3] Building PDREADF.exe via spec file...
python -m PyInstaller --clean --noconfirm PDREADF.spec
if errorlevel 1 goto :error

if not exist "dist\PDREADF.exe" (
    echo [ERROR] Build command finished but dist\PDREADF.exe was not produced.
    goto :error
)

echo.
echo [3/3] Verifying executable...
echo Build successful!
echo.
echo   Output:  dist\PDREADF.exe
echo.
echo To create a Windows installer, install Inno Setup and compile
echo installer.iss, or run the GitHub Actions workflow.
echo.
pause
exit /b 0

:error
echo.
echo [ERROR] Build failed. Check the output above.
pause
exit /b 1

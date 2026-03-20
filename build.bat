@echo off
setlocal

echo Installing project dependencies...
pip install -r requirements.txt

echo Installing PyInstaller...
pip install pyinstaller

echo Building PDREADF...
pyinstaller --clean --onefile --windowed --name PDREADF --icon=icon.ico --collect-all fitz pdreadf.py

echo.
echo Build complete. Find PDREADF.exe in the dist\ folder.
pause

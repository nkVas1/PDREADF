@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo Building PDREADF...
pyinstaller --onefile --windowed --name PDREADF --icon=icon.ico pdreadf.py

echo.
echo Build complete. Find PDREADF.exe in the dist\ folder.
pause

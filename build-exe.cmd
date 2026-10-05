@echo off
setlocal
cd /d "%~dp0"

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "YTDownPC.spec"
if errorlevel 1 exit /b %errorlevel%

for /f "tokens=2 delims==" %%V in ('findstr /b "APP_VERSION" version_info.py') do set "APP_VERSION=%%V"
set "APP_VERSION=%APP_VERSION: =%"
set "APP_VERSION=%APP_VERSION:"=%"
echo.
echo EXE: %~dp0dist\YTDownPC-v%APP_VERSION%.exe
endlocal

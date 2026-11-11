@echo off
setlocal
cd /d "%~dp0"
if not exist wheel-profile.json (
  echo Run Setup-Wheel.cmd first.
  pause
  exit /b 1
)
echo Paste the private prepared game folder from the mod loader, without quotes.
set /p "WHEEL_GAME_DIR=Private game folder: "
python wheel.py run --profile wheel-profile.json --output "%WHEEL_GAME_DIR%\MoonLab.Wheel.bin"
if errorlevel 1 pause

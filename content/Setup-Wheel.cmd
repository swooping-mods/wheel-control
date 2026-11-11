@echo off
setlocal
cd /d "%~dp0"
python wheel.py list
if errorlevel 1 goto failed
echo Copy each dinput: identifier from the list above.
set /p "WHEEL_ID=MOZA R9 identifier: "
set /p "PEDAL_ID=Simsonn Pro identifier: "
python wheel.py calibrate --wheel "%WHEEL_ID%" --pedals "%PEDAL_ID%" --profile wheel-profile.json
:failed
pause

@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
python "%SCRIPT_DIR%\split_buzz.py" --input "%SCRIPT_DIR%\719310__zazzsounddesign__dsgnsynth_digital-buzz-low-pitch-20_fc_sng.wav" --output-dir "%SCRIPT_DIR%"
endlocal
pause

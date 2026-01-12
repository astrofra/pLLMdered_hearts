@echo off
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%src\embed_vtt.py" %*
endlocal
pause

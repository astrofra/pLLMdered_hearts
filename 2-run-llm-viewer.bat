@echo off
setlocal

rem Start a simple HTTP server from project root on port 8000
start "" python -m http.server 8000

rem Give the server a moment to start
timeout /t 2 >nul

rem Launch Firefox in kiosk mode pointing to the viewer
start "" "C:\Program Files\Mozilla Firefox\firefox.exe" http://localhost:8000/www/index.html --kiosk

endlocal

@echo off
cd /d "%~dp0src"
set AIPPT_LIVE_MODE=1
echo Starting AI-Powered PPT Editor...
echo Please open http://127.0.0.1:8080 in your browser!
python -m aippt.canvas.app
pause

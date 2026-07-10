@echo off
setlocal
cd /d "%~dp0..\backend"

echo.
echo Autorox backend - http://127.0.0.1:8003
echo API docs:  http://127.0.0.1:8003/docs
echo App UI:    http://127.0.0.1:5173
echo.
echo Press Ctrl+C to stop.
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload

endlocal

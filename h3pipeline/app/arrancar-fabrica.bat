@echo off
rem La Fabrica: doble clic y abre http://127.0.0.1:8787
cd /d "%~dp0..\.."
if not exist "h3pipeline\app\logs" mkdir "h3pipeline\app\logs"
start "La Fabrica" /min cmd /c "C:\Python314\python.exe -X utf8 -u -m h3pipeline.app 8787 > h3pipeline\app\logs\servidor.log 2>&1"
timeout /t 4 >nul
start "" http://127.0.0.1:8787

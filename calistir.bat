@echo off
title MP3 DONUSTURUCUM (yerel)
cd /d "%~dp0"
echo MP3 DONUSTURUCUM baslatiliyor...
echo.
echo Guncellemeler kontrol ediliyor (bir kac saniye surebilir)...
python -m pip install -U yt-dlp --quiet --disable-pip-version-check
cd backend
start /B python app.py
timeout /t 4 /nobreak >nul
start http://127.0.0.1:8000
echo.
echo Tarayici acilmazsa: http://127.0.0.1:8000
pause

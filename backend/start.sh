#!/bin/sh
# PO Token sunucusunu arka planda başlat, sonra Flask API'yi çalıştır.
node /opt/bgutil/server/build/main.js --port 4416 --host 127.0.0.1 &
exec gunicorn --bind 0.0.0.0:$PORT --timeout 900 --workers 1 --threads 4 app:app

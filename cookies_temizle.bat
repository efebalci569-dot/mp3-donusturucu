@echo off
title Cookies temizle (Render icin)
cd /d "%~dp0"
if not exist cookies.txt (
  echo.
  echo  cookies.txt bulunamadi!
  echo  Indirdigin 627 KB'lik dosyayi bu klasorun icine
  echo  cookies.txt adiyla kopyala, sonra bunu tekrar calistir.
  echo.
  pause
  exit /b 1
)
python -c "lines=open('cookies.txt',encoding='utf-8',errors='replace').read().splitlines();keep=[l for l in lines if l.startswith('#') or any(d in l for d in ('youtube.com','google.com','googlevideo.com','gstatic.com','ytimg.com'))];open('cookies_render.txt','w',encoding='utf-8').write('\n'.join(keep)+'\n');print('girdi:',len(lines),'satir / cikti:',len(keep),'satir')"
echo.
echo  cookies_render.txt olustu.
echo  Bunu Not Defteri ile acip Render Secret File'a yapistir.
echo.
pause

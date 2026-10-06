# MP3 Dönüştürücüm

YouTube videolarını MP3'e dönüştüren ücretsiz masaüstü uygulaması. Windows, macOS ve Linux'ta
çalışır. Uygulama kullanıcının kendi bilgisayarında çalışır ve kendi tarayıcısında açılır;
indirme kullanıcının kendi internet bağlantısıyla yapılır.

**İndir:** [mp3-donusturucu.vercel.app](https://mp3-donusturucu.vercel.app)

## Neden masaüstü uygulaması?

İlk sürüm Vercel + Render üzerinde çalışan bir web sitesiydi. YouTube, veri merkezi IP
adreslerine video akışı vermediği için ("Sign in to confirm you're not a bot", "No video
formats found") sunucu tarafında indirme güvenilir değildi. Her kullanıcı kendi ev
internetinden indirince bu engel ortadan kalkıyor; sunucu, cookies ve hesap riski de kalmıyor.

## Nasıl çalışır

```
MP3Donusturucum (PyInstaller paketi)
  launcher.py   tek kopya kontrolü, boş port, tarayıcıyı açar, sekme kapanınca kapanır
  app.py        Flask, yalnızca 127.0.0.1
  converter.py  iş kuyruğu, yt-dlp çağrısı, ilerleme
  tools.py      yt-dlp ve Deno'yu ilk açılışta indirir / günceller, ffmpeg'i hazırlar
  frontend/     arayüz

Kullanıcı veri klasörü (Windows %LOCALAPPDATA%\MP3Donusturucum,
macOS ~/Library/Application Support/MP3Donusturucum, Linux ~/.local/share/mp3donusturucum)
  bin/          yt-dlp, deno, ffmpeg
  jobs/         geçici dosyalar
  log.txt       günlük (sorun bildirirken ekleyin)
```

- ffmpeg pakete gömülüdür (`imageio-ffmpeg`).
- yt-dlp ve Deno (yt-dlp'nin YouTube için kullandığı JavaScript çalıştırıcısı) ilk açılışta
  resmi GitHub sürümlerinden indirilir (~60 MB, bir kez). yt-dlp her açılışta kendini günceller.
- Sekme kapatıldıktan sonra, çalışan iş yoksa uygulama en geç üç dakika içinde kapanır.

## Geliştirme

```bash
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt -r requirements-dev.txt
.venv/Scripts/python backend/launcher.py      # uygulamayı çalıştır
.venv/Scripts/python -m pytest -q             # testler
```

Yerelde paket derlemek için:

```bash
.venv/Scripts/pyinstaller packaging/mp3donusturucum.spec --noconfirm
.venv/Scripts/python packaging/smoke_test.py dist/MP3Donusturucum/MP3Donusturucum.exe
```

## Yayınlama

Dört platform paketi GitHub Actions'ta derlenir (`.github/workflows/release.yml`). PR'larda
sadece derlenir; sürüm etiketi push edilince GitHub Release oluşturulur:

```bash
git tag v1.0.0
git push origin v1.0.0
```

İndirme sitesi (`site/`) Vercel'de yayınlanır ve her zaman en son Release'e bağlantı verir.

## Not

YouTube'dan içerik indirmek YouTube kullanım şartlarına aykırı olabilir; uygulama kişisel
kullanım için tasarlanmıştır.

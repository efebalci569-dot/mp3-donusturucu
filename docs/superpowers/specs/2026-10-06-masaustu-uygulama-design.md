# MP3 Dönüştürücüm — Masaüstü Uygulamasına Geçiş (Tasarım)

Tarih: 2026-10-06
Durum: Taslak — kullanıcı onayı bekleniyor

## 1. Amaç ve gerekçe

**Kullanıcının istediği:** Herkes siteye girip uygulamayı kullanabilsin; uygulama her
kullanıcının kendi bilgisayarına kurulsun, indirme orada yapılsın. Windows, macOS ve
Linux desteklensin. Kod imzalama için para harcanmasın (imzasız başlanacak).
Uygulama kullanıcının kendi tarayıcısında açılsın (yaklaşım A).

**Gerekçe:** Render'daki backend'e YouTube veri merkezi IP'si yüzünden video formatı
vermiyor ("No video formats found", cookies ile bot doğrulaması geçildikten sonra bile).
Aynı video, aynı yt-dlp sürümüyle ev internetinden sorunsuz formatları veriyor.
Her kullanıcı kendi ev IP'sinden indirince sunucu engeli, cookies, Google hesabı riski ve
sunucu maliyeti ortadan kalkar.

**Varsayımlar:**
- Kullanıcıların çoğu teknik değil: Python kurmadan, tek indirme + çift tıkla çalışmalı.
- Arayüz bugünkü sitenin aynısı kalır.
- Vercel'deki site bir "indir" sayfasına dönüşür.

**Başarı ölçütü:** Teknik olmayan bir kullanıcı siteye girip kendi işletim sistemine
uygun dosyayı indirir, kurulum rehberindeki adımlarla açar ve bir YouTube linkini MP3
olarak indirir — sunucu tarafında hiçbir şey çalışmadan.

## 2. Genel mimari

```
Kullanıcının bilgisayarı
┌─────────────────────────────────────────────────────────┐
│ MP3Donusturucum (PyInstaller paketi)                    │
│   launcher.py ── tek kopya kontrolü, port seçimi,       │
│                  tarayıcıyı açar, otomatik kapanma      │
│   app.py      ── Flask, yalnızca 127.0.0.1             │
│   converter.py── iş kuyruğu, yt-dlp çağrısı             │
│   tools.py    ── yt-dlp/deno indir-güncelle, ffmpeg bul │
│   frontend/   ── bugünkü arayüz (+ kurulum/güncelleme)  │
│   ffmpeg      ── pakete gömülü (imageio-ffmpeg)         │
├─────────────────────────────────────────────────────────┤
│ Kullanıcı veri klasörü                                  │
│   bin/yt-dlp[.exe], bin/deno[.exe]  (ilk açılışta iner) │
│   jobs/  (geçici dosyalar)   instance.json              │
└─────────────────────────────────────────────────────────┘
         ▲ tarayıcı: http://127.0.0.1:<port>

İnternet
  Vercel  ── site/ : tanıtım + işletim sistemine göre indirme düğmesi
  GitHub Releases ── paketler (GitHub Actions derler)
```

Render backend'i ve Vercel proxy'si (`api/proxy.py`) kaldırılır.

## 3. Bileşenler

### 3.1 `launcher.py` — giriş noktası
- Veri klasörünü belirler:
  - Windows: `%LOCALAPPDATA%\MP3Donusturucum`
  - macOS: `~/Library/Application Support/MP3Donusturucum`
  - Linux: `$XDG_DATA_HOME/mp3donusturucum` (yoksa `~/.local/share/mp3donusturucum`)
- **Tek kopya:** `instance.json` içindeki port `/api/health` ile yanıt veriyor ve yanıttaki
  `app` alanı bu uygulamayı gösteriyorsa tarayıcıda o adresi açar ve çıkar.
- Boş bir port seçer (`127.0.0.1:0`), `instance.json`'a yazar, Flask'ı (waitress değil,
  mevcut `threaded=True` geliştirme sunucusu yeterli; tek kullanıcı) başlatır, ardından
  `webbrowser.open` ile arayüzü açar.
- `--smoke-test` bayrağı: sunucuyu başlatır, `/api/health`'i kendisi çağırır, ffmpeg
  bulunduysa 0 ile çıkar. CI'da kullanılır; ağdan araç indirmez.

### 3.2 `tools.py` — dış araçların yönetimi
- **ffmpeg:** pakete gömülü `imageio-ffmpeg` ikilisi. Sıra: `FFMPEG_PATH` env → gömülü ikili
  → sistem PATH. Gömülü ikilinin adı standart değil (`ffmpeg-win-x86_64-v7.1.exe` gibi),
  bu yüzden veri klasöründe `bin/ffmpeg[.exe]` adıyla bir kopyası tutulur ve yt-dlp'ye o
  verilir. (ffprobe gerekmez; yt-dlp ses kodeğini ffmpeg ile de okuyabilir — uygulama
  sırasında doğrulanacak.)
- **yt-dlp:** resmi tek dosyalık sürüm, veri klasörüne `bin/` altına indirilir.
  - Windows `yt-dlp.exe`, macOS `yt-dlp_macos`, Linux `yt-dlp_linux`
    (`https://github.com/yt-dlp/yt-dlp/releases/latest/download/<ad>`).
  - Her açılışta arka planda `yt-dlp -U` çalışır; başarısız olursa mevcut sürümle devam edilir.
  - Resmi ikililer EJS çözücü betiklerini zaten içerir.
- **deno:** yt-dlp'nin varsayılan ve önerilen JS çalıştırıcısı (en az 2.3.0).
  - `deno-<hedef>.zip` (`x86_64-pc-windows-msvc`, `aarch64-apple-darwin`,
    `x86_64-apple-darwin`, `x86_64-unknown-linux-gnu`) indirilip açılır.
  - Yalnızca yoksa veya sürümü 2.3.0'dan düşükse indirilir.
  - yt-dlp'ye `--js-runtimes deno:<yol>` ile verilir (PATH'e güvenilmez).
- İndirme: önce `.part` dosyasına, bitince atomik yeniden adlandırma; macOS/Linux'ta
  çalıştırma izni (`chmod +x`). İlerleme yüzdesi `setup_state` içinde tutulur.
- İlk kurulum toplam ~55–75 MB indirme (yt-dlp 17–38 MB + deno ~40 MB), bir kez.

### 3.3 `app.py` — yerel API
Korunan uç noktalar: `/`, statik dosyalar, `/api/health`, `/api/convert`,
`/api/status/<id>`, `/api/download/<id>`. `/api/health` yanıtına tek kopya kontrolü için
`app: "mp3donusturucum"` ve `version` alanları eklenir.

Yeni uç noktalar:
- `GET /api/setup` → `{ready, steps: {ytdlp, deno, ffmpeg}: {state, progress}, error,
  update: {available, version, url} | null}`
- `POST /api/heartbeat` → arayüz her 10 sn çağırır.

Kaldırılan: `/api/debug`, CORS (`flask-cors`).

**Güvenlik:**
- Sunucu yalnızca `127.0.0.1`'e bağlanır.
- `Host` başlığı `127.0.0.1:<port>` veya `localhost:<port>` değilse 403 (DNS rebinding'e karşı).
- CORS yok; `/api/convert` JSON gövde istediği için başka sitelerden basit form
  isteğiyle tetiklenemez.

### 3.4 `converter.py` — sadeleştirilmiş
Kalanlar: iş kuyruğu (`ThreadPoolExecutor`), ilerleme ayrıştırma, URL doğrulama, dosya adı
temizleme, zaman aşımı, TTL temizliği, kullanıcı dostu hata mesajları.

Çıkarılanlar (ev IP'sinde gereksiz sunucu yamaları): cookies, PO Token / bgutil,
Invidious yedeği, 7 istemcili deneme döngüsü, `--impersonate`, `YTDLP_PROXY`,
`--remote-components`, `--force-ipv4`.

yt-dlp tek bir `--dump-json` + tek bir indirme çağrısıyla, varsayılan istemcilerle çalışır.
yt-dlp ve ffmpeg yolları `tools.py`'den gelir. İşler veri klasöründeki `jobs/` altında tutulur.

### 3.5 Arayüz (`frontend/`)
- Açılışta `/api/setup` sorgulanır. Hazır değilse "İlk kurulum: araçlar indiriliyor (%x)"
  gösterilir, dönüştür düğmesi kapalı kalır.
- Yeni sürüm varsa üstte "Yeni sürüm var — indir" şeridi (GitHub Releases bağlantısı).
- Her 10 sn `/api/heartbeat`.
- `parseJsonSafe`'teki "BACKEND_URL yanlış" ipucu kaldırılır (artık proxy yok).

### 3.6 Yaşam döngüsü ve otomatik kapanma
- İlk 120 sn bekleme payı (tarayıcı açılsın diye).
- Son heartbeat'ten 180 sn geçmişse **ve** çalışan iş yoksa uygulama kendini kapatır,
  `instance.json`'ı siler. Sekme kapatılınca en geç üç dakika içinde kapanır.
  (180 sn, tarayıcıların arka plan sekmelerindeki zamanlayıcıları dakikada bire
  düşürmesine karşı pay bırakır; 60 sn açık sekmeyi kapatma riski taşırdı.)
- Pencere/konsol yok (Windows ve macOS'ta `--windowed`; macOS'ta `LSUIElement` ile Dock
  simgesi de yok, çünkü uygulamanın penceresi yok). Kullanıcı tekrar tıklarsa
  tek kopya kontrolü mevcut sekmeyi açar.
- Bilinen sınır: macOS çalışan bir uygulamaya çift tıklanınca yeni süreç başlatmaz;
  sekme kapatıldıktan sonraki en fazla üç dakika içinde tekrar açma girişimi bir şey
  yapmaz.

### 3.7 Yeni sürüm kontrolü
- Açılışta bir kez `api.github.com/repos/efebalci569-dot/mp3-donusturucu/releases/latest`
  okunur, etiket uygulama sürümünden yeniyse arayüze bildirilir.
- Ağ hatası sessizce yok sayılır. Otomatik güncelleme yok, sadece bildirim.

## 4. Paketleme ve dağıtım

PyInstaller **onedir** modu: her açılışta geçici klasöre açma yok, daha hızlı başlar ve
antivirüs yanlış alarmı daha az.

| Platform | Derleme sunucusu | Dosya (Release'te sabit ad) |
|---|---|---|
| Windows x64 | `windows-latest` | `MP3Donusturucum-Windows-Kurulum.exe` (Inno Setup; yönetici izni istemez, `%LOCALAPPDATA%\Programs`'a kurar, Başlat menüsü + isteğe bağlı masaüstü kısayolu, kaldırıcı) |
| macOS Apple Silicon | `macos-15` | `MP3Donusturucum-Mac-AppleSilicon.zip` (`.app`) |
| macOS Intel | `macos-15-intel` (Ağustos 2027'ye kadar destekli) | `MP3Donusturucum-Mac-Intel.zip` (`.app`) |
| Linux x64 | `ubuntu-22.04` (eski glibc ile uyumluluk) | `MP3Donusturucum-Linux-x64.tar.gz` |

- **GitHub Actions** (`.github/workflows/release.yml`): `v*` etiketi push edilince dört
  platformda derler, `--smoke-test` çalıştırır, dosyaları GitHub Release'e yükler.
  Sürüm numarası etiketten `version.py`'ye yazılır. Derlemede Python 3.12.
- CI gerçek YouTube indirmesi yapmaz (veri merkezi IP'si engelli); sadece açılış ve
  ffmpeg kontrolü.
- macOS paketleri PyInstaller'ın varsayılan ad-hoc imzasıyla imzalanır (Apple Silicon'da
  çalışabilmek için gerekli); notarize edilmez.

## 5. İndirme sitesi (Vercel)

- Yeni `site/` klasörü: tanıtım, işletim sistemine göre seçilen büyük indirme düğmesi,
  diğer platformların listesi. Bağlantılar sabit:
  `https://github.com/efebalci569-dot/mp3-donusturucu/releases/latest/download/<dosya>`
- Platform başına ilk açılış rehberi:
  - **Windows:** SmartScreen'de "Ek bilgi" → "Yine de çalıştır".
  - **macOS (Sequoia ve sonrası):** Uygulamayı bir kez açmayı dene → Sistem Ayarları →
    Gizlilik ve Güvenlik → "Yine de Aç" → yönetici parolası. Sonraki açılışlar normal.
  - **Linux:** arşivi aç, çıkan klasördeki `MP3Donusturucum` dosyasını çalıştır
    (terminalden `./MP3Donusturucum`).
- `vercel.json`: `outputDirectory: site`; `rewrites` ve `functions` kaldırılır.
- Bilgi notu: YouTube'dan indirme YouTube kullanım şartlarına aykırı olabilir; kişisel
  kullanım içindir (README'deki not korunur).

## 6. Kaldırılanlar ve kullanıcının yapacakları

Depodan silinecekler: `api/` (proxy), `backend/Dockerfile`, `backend/start.sh`,
`cookies_temizle.bat`, `calistir.bat` (yerine geliştirme için `python launcher.py`),
gereksiz bağımlılıklar (`flask-cors`, `bgutil-ytdlp-pot-provider`, `curl_cffi`,
`gunicorn`, Python `yt-dlp` paketi).

**Kullanıcının elle yapması gerekenler** (güvenlik açısından önemli):
1. Render'daki servisi ve `appcookies.txt` gizli dosyasını silmek.
2. Bu cookies bir Google oturumu olduğundan Google Hesabı → Güvenlik → cihazlarından
   o oturumu kapatmak.
3. Bilgisayardaki `cookies.txt`, `cookies_render.txt` ve indirilen cookies dosyasını silmek.
4. Vercel'deki `BACKEND_URL` ortam değişkenini kaldırmak.

## 7. Hata yönetimi

| Durum | Davranış |
|---|---|
| İlk kurulumda internet yok / GitHub erişilemiyor | Kurulum ekranında anlaşılır hata + "Tekrar dene" düğmesi |
| `yt-dlp -U` başarısız | Sessizce mevcut sürümle devam, günlüğe yazılır |
| ffmpeg bulunamadı | Kurulum ekranında hata (paket bozuk demektir) |
| Port dolu / instance.json bayat | Yeni port seçilir, bayat dosya üzerine yazılır |
| İndirme hatası | Bugünkü kullanıcı dostu mesajlar |
| 403 veya "No video formats" | Arka planda `yt-dlp -U` başlatılır (açılıştaki güncelleme dahil en fazla 30 dakikada bir); kullanıcıya "yt-dlp güncelleniyor, birazdan tekrar deneyin" denir |
| Antivirüs `bin/` içindeki dosyayı silerse | Bir sonraki açılışta yeniden indirilir |

Günlük dosyası: veri klasöründe `log.txt` (son 1 MB tutulur), sorun bildirmek için.

## 8. Test

- **Birim testleri (pytest):** veri klasörü çözümleme (3 işletim sistemi), platforma göre
  dosya adları, araç indirme/açma (sahte HTTP ile), deno sürüm karşılaştırma, `Host`
  başlığı kontrolü, heartbeat/otomatik kapanma (enjekte edilebilir saat ile), yt-dlp komut
  oluşturma.
- **CI duman testi:** dört platformda paket açılıyor, `/api/health` yanıt veriyor, ffmpeg
  bulunuyor.
- **Elle uçtan uca test:** Windows'ta kurulum dosyasıyla kurup gerçek video indirme
  (kullanıcının bilgisayarında yapılabilir).
- **Doğrulanamayan:** macOS ve Linux'ta gerçek indirme; Mac/Linux kullanan bir test kişisi
  gerekir. Bu açıkça belirtilecek.

## 9. Kapsam dışı (YAGNI)

Uygulamanın kendini otomatik güncellemesi, kod imzalama/notarization, Linux ARM ve
Windows ARM derlemeleri (Windows ARM x64 emülasyonuyla çalışır), playlist desteği,
indirme klasörü seçimi, sistem tepsisi simgesi, kendi penceresi (pywebview).

## 10. Çalışma ortamı notu

Yerel proje klasörü şu an bir git çalışma kopyası değil (ev klasöründeki ayrı bir
deponun içinde, izlenmiyor). Uygulama sırasında çalışma, GitHub deposunun düzgün bir
kopyasında yapılacak; bu belge ilk uygulama commit'iyle birlikte depoya eklenecek.

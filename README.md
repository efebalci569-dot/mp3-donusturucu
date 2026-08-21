# MP3 Dönüştürücü

YouTube bağlantılarından ses dosyası indirip MP3 formatına dönüştüren, modern bir web arayüzüne sahip full-stack uygulama.

> **Mimari notu:** Proje iki parçalı çalışır. Frontend ve API proxy Vercel’de, FFmpeg ve yt-dlp kullanan asıl dönüştürme servisi ise sürekli çalışan Docker backend üzerinde yayınlanır. MP3 dönüştürme işlemini yalnızca Vercel Serverless Function içine koymak güvenilir değildir; bu nedenle backend ayrı tutulmuştur.

## Özellikler

| Özellik | Açıklama |
|---|---|
| YouTube URL doğrulama | Yalnızca desteklenen YouTube bağlantı biçimleri kabul edilir. |
| MP3 dönüştürme | yt-dlp ile kaynak alınır, FFmpeg ile MP3 çıktısı hazırlanır. |
| Asenkron iş akışı | Dönüştürme başlatıldığında anında `job_id` döner; frontend ilerlemeyi sorgular. |
| İlerleme göstergesi | Kullanıcı dönüştürme yüzdesini ve işlem durumunu görür. |
| Geçici dosya temizliği | Eski işler otomatik olarak temizlenir. |
| Docker backend | FFmpeg, Node.js ve Python bağımlılıkları Docker imajında tanımlıdır. |
| Vercel frontend | Statik arayüz ve API proxy Vercel üzerinden yayınlanabilir. |

## Proje Mimarisi

```text
Kullanıcı tarayıcısı
        │
        │ /api/convert, /api/status, /api/download
        ▼
Vercel
  ├── frontend/          Statik kullanıcı arayüzü
  └── api/proxy.py       BACKEND_URL üzerinden proxy
        │
        ▼
Docker Backend
  ├── backend/app.py     Flask API
  ├── backend/converter.py
  ├── yt-dlp             Video/ses kaynağını alır
  └── FFmpeg             MP3 dönüştürmesini yapar
```

## Klasör Yapısı

```text
.
├── api/
│   ├── proxy.py
│   └── requirements.txt
├── backend/
│   ├── app.py
│   ├── converter.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── vercel.json
├── calistir.bat
├── .gitignore
└── README.md
```

## Yerel Kurulum

### Gereksinimler

Yerel kullanım için Python 3.11 veya üzeri, FFmpeg ve Node.js gereklidir. Python paketlerini aşağıdaki komutla kurabilirsin:

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Backend varsayılan olarak `http://127.0.0.1:8000` adresinde açılır. Windows’ta proje klasöründeki `calistir.bat` dosyası da kullanılabilir.

## API Endpoint’leri

| Endpoint | Method | Açıklama |
|---|---:|---|
| `/api/health` | `GET` | Backend ve FFmpeg durumunu kontrol eder. |
| `/api/convert` | `POST` | JSON gövdesindeki YouTube URL’si için yeni iş başlatır. |
| `/api/status/<job_id>` | `GET` | İşin sırasını, ilerlemesini veya hata durumunu döndürür. |
| `/api/download/<job_id>` | `GET` | Hazır MP3 dosyasını indirir. |

Örnek istek:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

## Docker ile Backend Çalıştırma

```bash
cd backend
docker build -t mp3-donusturucu-api .
docker run --rm -p 8000:8000 mp3-donusturucu-api
```

Dockerfile, backend için FFmpeg, Node.js, Python paketleri ve Gunicorn kurulumunu içerir. Üretim ortamında backend’in Dockerfile’ı `backend` klasörü bağlamından build edilmelidir.

## Backend’i Render, Railway veya Fly.io’da Yayınlama

Vercel, uzun süren FFmpeg işlemleri için uygun bir backend çalışma ortamı değildir. Bu nedenle backend’i Docker destekleyen bir platforma yayınlamak gerekir.

Önerilen ayarlar:

| Ayar | Değer |
|---|---|
| Runtime | Docker |
| Dockerfile | `backend/Dockerfile` |
| Docker context | `backend` klasörü |
| Port | Platformun verdiği `PORT` değişkeni |
| Health endpoint | `/api/health` |
| `JOBS_DIR` | `/tmp/mp3_jobs` |
| `MAX_CONCURRENT_JOBS` | `2` |
| `JOB_TTL_SECONDS` | `1800` |
| `DOWNLOAD_TIMEOUT_SECONDS` | `600` |

Backend yayınlandıktan sonra public URL’yi not al. Örnek:

```text
https://mp3-donusturucu-api.onrender.com
```

## Vercel’de Frontend Yayını

Bu repository’yi Vercel’e bağlarken frontend’in çalışması için Vercel Project Settings → Environment Variables bölümüne aşağıdaki değişkeni ekle:

| Değişken | Değer |
|---|---|
| `BACKEND_URL` | Yayınlanan backend URL’si; sonuna `/` koyma |

Örnek:

```text
BACKEND_URL=https://mp3-donusturucu-api.onrender.com
```

Environment variable eklendikten sonra Vercel’de yeniden deploy yapılmalıdır. Frontend, `/api/*` çağrılarını `api/proxy.py` üzerinden backend’e yönlendirir.

## GitHub’a Yükleme

```bash
git init
git add .
git commit -m "MP3 dönüştürücü projesi"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADIN/mp3-donusturucu.git
git push -u origin main
```

`.gitignore` nedeniyle `.env`, geçici dosyalar, `downloads/` klasörü ve MP3 çıktıları repository’ye yüklenmez.

## Güvenlik ve Kullanım Notları

Kullanıcıdan alınan URL doğrulanır ve işletim sistemi shell komutuna doğrudan eklenmeden subprocess argümanlarıyla işlenir. Gizli anahtarlar veya çerez dosyaları repository’ye yüklenmemelidir. YouTube içeriklerini indirme ve dönüştürme işlemleri ilgili platformun kullanım şartlarına ve telif kurallarına uygun şekilde kullanılmalıdır.

> Bu proje eğitim ve kişisel kullanım amacıyla hazırlanmıştır. İçeriklerin indirilmesi veya dağıtılması konusunda ilgili hak sahiplerinin izinlerine ve platform kurallarına dikkat et.

## Lisans

Bu repository’ye lisans eklenmemiştir. Projeyi herkese açık şekilde dağıtacaksan kullanım koşullarını ayrıca belirleyen bir lisans eklemen önerilir.

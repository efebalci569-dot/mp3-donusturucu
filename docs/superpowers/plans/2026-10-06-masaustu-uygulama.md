# MP3 Dönüştürücüm Masaüstü Uygulaması — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render/Vercel'e bağımlı web uygulamasını, her kullanıcının kendi bilgisayarında
çalışan ve kendi tarayıcısında açılan bir masaüstü uygulamasına dönüştürmek; Vercel'deki
siteyi indirme sayfası yapmak.

**Architecture:** Mevcut Flask backend + arayüz PyInstaller (onedir) ile paketlenir.
`launcher.py` yerel sunucuyu `127.0.0.1`'de başlatıp tarayıcıyı açar; `tools.py` ilk
açılışta yt-dlp ve Deno'yu indirir, ffmpeg pakete gömülüdür. GitHub Actions dört platform
paketini derleyip GitHub Releases'e koyar; `site/` bu dosyalara bağlantı verir.

**Tech Stack:** Python 3.12 (CI) / 3.11 (yerel venv), Flask, imageio-ffmpeg, PyInstaller,
Inno Setup 6, GitHub Actions, pytest, düz HTML/CSS/JS.

**Spec:** `docs/superpowers/specs/2026-10-06-masaustu-uygulama-design.md`

## Global Constraints

- Depo: `efebalci569-dot/mp3-donusturucu`; tüm iş `masaustu-uygulama` dalında.
- Çalışma zamanı bağımlılıkları yalnızca `flask>=3.0` ve `imageio-ffmpeg>=0.6`.
  Geliştirme: `pytest>=8`, `pyinstaller>=6.10`.
- Sunucu yalnızca `127.0.0.1`'e bağlanır; `Host` başlığı `127.0.0.1:<port>` veya
  `localhost:<port>` değilse 403.
- `APP_ID = "mp3donusturucum"`. Veri klasörü: Windows `%LOCALAPPDATA%\MP3Donusturucum`,
  macOS `~/Library/Application Support/MP3Donusturucum`, Linux
  `$XDG_DATA_HOME/mp3donusturucum` (yoksa `~/.local/share/mp3donusturucum`).
- yt-dlp: `https://github.com/yt-dlp/yt-dlp/releases/latest/download/{yt-dlp.exe|yt-dlp_macos|yt-dlp_linux}`.
- Deno: `https://github.com/denoland/deno/releases/latest/download/deno-<hedef>.zip`, en az
  2.3.0; yt-dlp'ye `--js-runtimes deno:<yol>` ile verilir.
- Her `subprocess` çağrısı `tools.hidden_subprocess_kwargs()` alır (Windows'ta konsol
  penceresi açılmasın).
- Süreler: bekleme payı 120 sn, boşta kapanma 180 sn, heartbeat 10 sn, `yt-dlp -U` en
  fazla 1800 sn'de bir, iş zaman aşımı 600 sn, iş TTL 1800 sn, eşzamanlı iş 2,
  günlük 1 MB.
- Release dosya adları: `MP3Donusturucum-Windows-Kurulum.exe`,
  `MP3Donusturucum-Mac-AppleSilicon.zip`, `MP3Donusturucum-Mac-Intel.zip`,
  `MP3Donusturucum-Linux-x64.tar.gz`.
- Arayüz metinleri Türkçe. Commit mesajları kısa Türkçe ve
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` satırıyla biter.
- Push, PR, etiket ve birleştirme işlemlerinden önce kullanıcı onayı alınır.

## Review Focus

1. **Arka plandaki sekme:** Tarayıcı zamanlayıcıları dakikada bire düşürünce uygulama
   açık sekmeyi kapatmamalı → Task 5 `test_background_tab_throttling_does_not_exit`.
2. **Windows'ta konsol pencereleri:** Paketlenmiş uygulamada her yt-dlp/deno/ffmpeg
   çağrısı siyah pencere açmamalı → Task 2/3/4 `..._hidden` testleri.
3. **`sys.stdout`/`sys.stderr` = None** (pencereli PyInstaller modu): günlük yazma
   çökmemeli → Task 7 `test_smoke_test_with_none_streams`.
4. **Türkçe karakterli/boşluklu yollar ve başlıklar** (kullanıcı adı "Gökçe", OneDrive,
   "Şarkı" başlıklı video) → Task 2 `test_download_writes_file_and_reports_progress`
   (`ş ğ ü klasör`), Task 4 `test_job_success_flow`, Task 6
   `test_download_non_ascii_filename_header`.
5. **İlk kurulumda yarıda kesilen indirme:** Yarım dosya kurulu sayılmamalı, sonraki
   açılışta yeniden inmeli → Task 2 `test_download_failure_leaves_no_file`.

---

### Task 1: Çalışma kopyası, geliştirme ortamı ve `paths.py`

**Files:**
- Create: `backend/paths.py`, `backend/version.py`, `tests/test_paths.py`, `pytest.ini`, `requirements-dev.txt`
- Modify: `backend/requirements.txt`, `.gitignore`

**Interfaces:**
- Produces: `paths.APP_ID: str = "mp3donusturucum"`, `paths.APP_NAME: str = "MP3Donusturucum"`,
  `paths.data_dir(system: str | None = None, env: Mapping[str, str] | None = None, home: Path | None = None) -> Path`,
  `paths.resource_dir() -> Path` (dondurulmuşsa `sys._MEIPASS`, değilse depo kökü),
  `paths.bin_dir(base: Path) -> Path` (`base/"bin"`), `paths.jobs_dir(base)` (`base/"jobs"`),
  `paths.instance_file(base)` (`base/"instance.json"`), `paths.log_file(base)` (`base/"log.txt"`).
  Bu fonksiyonlar klasör oluşturmaz. `version.__version__ = "0.0.0-dev"`.

- [ ] **Step 1: Proje klasörünü depo kopyasına çevir**

```bash
cd "/c/Users/efeba/OneDrive/Desktop/yazılım/dönüştürücü"
git init -b main
git remote add origin https://github.com/efebalci569-dot/mp3-donusturucu.git
git fetch origin
git reset origin/main
git checkout -- backend/converter.py
git checkout -b masaustu-uygulama
git status --short
```
Expected: yalnızca `?? docs/` görünür (`api/proxy.py` origin ile aynı).

- [ ] **Step 2: Bağımlılıklar ve venv**

`backend/requirements.txt` → `flask>=3.0`, `imageio-ffmpeg>=0.6`.
`requirements-dev.txt` → `pytest>=8`, `pyinstaller>=6.10`.
`pytest.ini` → `[pytest]` / `pythonpath = backend` / `testpaths = tests`.
`.gitignore`'a `build/` ve `dist/` ekle.

```bash
py -3.11 -m venv .venv && source .venv/Scripts/activate
python -m pip install -r backend/requirements.txt -r requirements-dev.txt
```

- [ ] **Step 3: Başarısız testleri yaz** (`tests/test_paths.py`)

```python
def test_data_dir_windows():
    assert paths.data_dir("Windows", {"LOCALAPPDATA": r"C:\U\AppData\Local"}, Path("/h")) \
        == Path(r"C:\U\AppData\Local") / "MP3Donusturucum"
def test_data_dir_mac():
    assert paths.data_dir("Darwin", {}, Path("/h")) == Path("/h/Library/Application Support/MP3Donusturucum")
def test_data_dir_linux_xdg():
    assert paths.data_dir("Linux", {"XDG_DATA_HOME": "/x"}, Path("/h")) == Path("/x/mp3donusturucum")
def test_data_dir_linux_default():
    assert paths.data_dir("Linux", {}, Path("/h")) == Path("/h/.local/share/mp3donusturucum")
def test_resource_dir_dev():
    assert (paths.resource_dir() / "frontend" / "index.html").is_file()
def test_resource_dir_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/m", raising=False)
    assert paths.resource_dir() == Path("/m")
```

- [ ] **Step 4: Çalıştır, başarısız olduğunu gör**

Run: `python -m pytest tests/test_paths.py -v` → Expected: FAIL (`No module named 'paths'`)

- [ ] **Step 5: `backend/paths.py` ve `backend/version.py`'yi yaz** (Interfaces'teki imzalar)

- [ ] **Step 6: Çalıştır** → `python -m pytest tests/test_paths.py -v` → Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add .gitignore pytest.ini requirements-dev.txt backend/requirements.txt backend/paths.py backend/version.py tests/ docs/
git commit -m "masaustu: paths modulu, gelistirme ortami, tasarim ve plan"
```

---

### Task 2: `tools.py` (1) — platform dosya adları, güvenli indirme, kurulum durumu, ffmpeg

**Files:**
- Create: `backend/tools.py`, `tests/test_tools_basic.py`, `tests/helpers.py`

`tests/helpers.py` (sonraki görevlerde de kullanılır): `FakeResponse`, `fake_opener(resp)`,
`zip_bytes(files: dict[str, bytes]) -> bytes`, `fail_run(*a, **k)` (çağrılırsa `AssertionError`),
`wait_until(pred, timeout=2.0)` (10 ms aralıkla bekler, süre dolarsa `AssertionError`),
`json_opener(obj)`, `raising_opener(url, timeout)` (`OSError` atar), `boom(*a)` (`RuntimeError` atar).

**Interfaces:**
- Produces:
  - `class ToolError(Exception)`, `class UnsupportedPlatform(ToolError)`
  - `hidden_subprocess_kwargs() -> dict` → Windows'ta `{"creationflags": subprocess.CREATE_NO_WINDOW}`, diğerlerinde `{}`
  - `exe_name(name: str, system: str) -> str` → Windows'ta `.exe` ekler
  - `ytdlp_asset(system: str) -> str`, `deno_asset(system: str, machine: str) -> str`
  - `download(url: str, dest: Path, on_progress: Callable[[int], None], opener=urllib.request.urlopen) -> None`
    → `dest` klasörünü oluşturur, `dest.with_name(dest.name + ".part")`'a 64 KB parçalarla yazar,
    `Content-Length` varsa yüzde bildirir, bitince `os.replace`; POSIX'te `chmod 0o755`;
    hata olursa `.part`'ı silip istisnayı yükseltir. `opener(url, timeout=60)` çağrılır.
  - `class SetupState` (thread-safe): `STEPS = ("ffmpeg", "ytdlp", "deno")`,
    `set_step(name: str, state: str, progress: int = 0)` (`"pending"|"downloading"|"ready"|"error"`),
    `fail(message: str)`, `reset()`, `ready: bool` (üçü de `"ready"` ve hata yok),
    `to_dict() -> {"ready": bool, "steps": {ad: {"state": str, "progress": int}}, "error": str | None}`
  - `bundled_ffmpeg() -> Path | None` → `FFMPEG_PATH` env → `imageio_ffmpeg.get_ffmpeg_exe()` → `shutil.which("ffmpeg")`
  - `ensure_ffmpeg(bin_dir: Path, state: SetupState, system: str) -> Path` → `bin_dir/exe_name("ffmpeg")`
    yoksa veya boyutu gömülüden farklıysa kopyalar (`shutil.copy2`); kaynak yoksa
    `ToolError(FFMPEG_MISSING_MSG)`.
  - `FFMPEG_MISSING_MSG = "FFmpeg bulunamadı; uygulama paketi bozuk olabilir. Uygulamayı yeniden indirip kur."`

- [ ] **Step 1: Başarısız testleri yaz**

Testte sahte yanıt: `FakeResponse(data: bytes, fail_after: int | None = None)` — bağlam
yöneticisi, `.headers = {"Content-Length": str(len(data))}`, `.read(n)`; `fail_after` bayt
okunduktan sonra `OSError` atar. `fake_opener(resp)` → `lambda url, timeout: resp`.

```python
def test_ytdlp_asset():
    assert [tools.ytdlp_asset(s) for s in ("Windows", "Darwin", "Linux")] == ["yt-dlp.exe", "yt-dlp_macos", "yt-dlp_linux"]
@pytest.mark.parametrize("system,machine,asset", [
    ("Windows", "AMD64", "deno-x86_64-pc-windows-msvc.zip"),
    ("Darwin", "arm64", "deno-aarch64-apple-darwin.zip"),
    ("Darwin", "x86_64", "deno-x86_64-apple-darwin.zip"),
    ("Linux", "x86_64", "deno-x86_64-unknown-linux-gnu.zip"),
    ("Linux", "aarch64", "deno-aarch64-unknown-linux-gnu.zip")])
def test_deno_asset(system, machine, asset): assert tools.deno_asset(system, machine) == asset
def test_deno_asset_unsupported():
    with pytest.raises(tools.UnsupportedPlatform): tools.deno_asset("Linux", "armv7l")
def test_download_writes_file_and_reports_progress(tmp_path):
    dest = tmp_path / "ş ğ ü klasör" / "yt-dlp"; seen = []
    tools.download("u", dest, seen.append, opener=fake_opener(FakeResponse(b"x" * 200_000)))
    assert dest.read_bytes() == b"x" * 200_000 and seen[-1] == 100
    assert not dest.with_name("yt-dlp.part").exists()
    if os.name != "nt": assert os.access(dest, os.X_OK)
def test_download_failure_leaves_no_file(tmp_path):
    dest = tmp_path / "yt-dlp"
    with pytest.raises(OSError):
        tools.download("u", dest, lambda p: None, opener=fake_opener(FakeResponse(b"x" * 200_000, fail_after=65_536)))
    assert not dest.exists() and not dest.with_name("yt-dlp.part").exists()
def test_setup_state_ready_and_dict():
    s = tools.SetupState(); assert s.ready is False
    for n in s.STEPS: s.set_step(n, "ready", 100)
    assert s.ready is True and s.to_dict()["steps"]["deno"] == {"state": "ready", "progress": 100}
    s.fail("hata"); assert s.ready is False and s.to_dict()["error"] == "hata"
def test_ensure_ffmpeg_copies_bundled(tmp_path, monkeypatch):
    src = tmp_path / "ffmpeg-win-x86_64-v7.1.exe"; src.write_bytes(b"ff")
    monkeypatch.setattr(tools, "bundled_ffmpeg", lambda: src)
    out = tools.ensure_ffmpeg(tmp_path / "bin", tools.SetupState(), "Windows")
    assert out == tmp_path / "bin" / "ffmpeg.exe" and out.read_bytes() == b"ff"
def test_ensure_ffmpeg_missing_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "bundled_ffmpeg", lambda: None)
    with pytest.raises(tools.ToolError, match="FFmpeg bulunamadı"):
        tools.ensure_ffmpeg(tmp_path, tools.SetupState(), "Linux")
def test_hidden_kwargs():
    expected = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    assert tools.hidden_subprocess_kwargs() == expected
```

- [ ] **Step 2: Çalıştır** → `python -m pytest tests/test_tools_basic.py -v` → Expected: FAIL (`No module named 'tools'`)
- [ ] **Step 3: `backend/tools.py`'de Interfaces'teki öğeleri yaz**
- [ ] **Step 4: Çalıştır** → Expected: tümü PASS
- [ ] **Step 5: Commit** → `git add backend/tools.py tests/test_tools_basic.py && git commit -m "masaustu: arac indirme ve kurulum durumu"`

---

### Task 3: `tools.py` (2) — yt-dlp ve Deno kurulumu, `run_setup`, `YtdlpUpdater`

**Files:**
- Modify: `backend/tools.py`
- Create: `tests/test_tools_setup.py`

**Interfaces:**
- Consumes: Task 2'deki her şey.
- Produces:
  - `@dataclass(frozen=True) class ToolPaths: ytdlp: Path; deno: Path; ffmpeg: Path`
  - `YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/{asset}"`,
    `DENO_URL = "https://github.com/denoland/deno/releases/latest/download/{asset}"`,
    `MIN_DENO = (2, 3, 0)`, `YTDLP_UPDATE_INTERVAL = 1800`
  - `SETUP_NETWORK_MSG = "Araçlar indirilemedi. İnternet bağlantını kontrol edip Tekrar dene'ye bas."`
  - `ensure_ytdlp(bin_dir: Path, state: SetupState, system: str, opener=...) -> Path` —
    dosya varsa ve boyutu > 0 ise indirmez.
  - `parse_deno_version(text: str) -> tuple[int, int, int] | None`
  - `ensure_deno(bin_dir: Path, state: SetupState, system: str, machine: str, opener=..., run=subprocess.run) -> Path` —
    varsa `[deno, "--version"]` ile sürümü okur (`run(..., capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs())`);
    yoksa veya `< MIN_DENO` ise zip'i `bin_dir/"deno.zip"`'e indirir, `exe_name("deno")` üyesini
    çıkarır, POSIX'te `chmod 0o755`, zip'i siler.
  - `run_setup(state: SetupState, bin_dir: Path, system: str | None = None, machine: str | None = None, opener=..., run=...) -> ToolPaths | None` —
    sırası ffmpeg → yt-dlp → deno; `state.reset()` ile başlar; `ToolError` → `state.fail(str(e))`,
    `OSError`/`URLError` → `state.fail(SETUP_NETWORK_MSG)`; hata varsa `None`.
  - `class YtdlpUpdater(ytdlp: Path, clock=time.monotonic, run=subprocess.run)`:
    `trigger() -> bool` — çalışan güncelleme yoksa ve son başlatmadan `YTDLP_UPDATE_INTERVAL`
    geçtiyse daemon thread'de `run([str(ytdlp), "-U"], capture_output=True, timeout=300, **hidden_subprocess_kwargs())`
    çalıştırır ve `True` döner; aksi halde `False`. `is_running: bool`. Hata günlüğe yazılır, yükseltilmez.

- [ ] **Step 1: Başarısız testleri yaz**

```python
def test_ensure_ytdlp_downloads_when_missing(tmp_path):
    urls = []
    def opener(url, timeout): urls.append(url); return FakeResponse(b"bin")
    p = tools.ensure_ytdlp(tmp_path, tools.SetupState(), "Linux", opener=opener)
    assert urls == ["https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"]
    assert p == tmp_path / "yt-dlp" and p.read_bytes() == b"bin"
def test_ensure_ytdlp_skips_when_present(tmp_path):
    (tmp_path / "yt-dlp.exe").write_bytes(b"bin")
    def opener(url, timeout): raise AssertionError("indirmemeliydi")
    assert tools.ensure_ytdlp(tmp_path, tools.SetupState(), "Windows", opener=opener) == tmp_path / "yt-dlp.exe"
def test_parse_deno_version():
    assert tools.parse_deno_version("deno 2.9.7 (stable, release, x86_64-pc-windows-msvc)\nv8 14.0") == (2, 9, 7)
    assert tools.parse_deno_version("garip çıktı") is None
def test_ensure_deno_extracts_zip(tmp_path):  # zip_bytes({"deno": b"DENO"}) yardımcı fonksiyonu
    p = tools.ensure_deno(tmp_path, tools.SetupState(), "Linux", "x86_64",
                          opener=fake_opener(FakeResponse(zip_bytes({"deno": b"DENO"}))), run=fail_run)
    assert p.read_bytes() == b"DENO" and not (tmp_path / "deno.zip").exists()
def test_ensure_deno_replaces_old_version(tmp_path): ...   # mevcut deno + run → "deno 2.2.0" ⇒ opener çağrılır
def test_ensure_deno_keeps_new_enough_hidden(tmp_path):
    # mevcut deno + run → "deno 2.3.0" ⇒ opener çağrılmaz; run'a giden kwargs hidden_subprocess_kwargs()'ı içerir
def test_run_setup_network_error_sets_message(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "bundled_ffmpeg", lambda: ffmpeg_stub)   # tmp'de sahte dosya
    def opener(url, timeout): raise urllib.error.URLError("yok")
    assert tools.run_setup(st := tools.SetupState(), tmp_path, "Linux", "x86_64", opener=opener, run=fail_run) is None
    assert st.to_dict()["error"] == tools.SETUP_NETWORK_MSG and st.ready is False
def test_run_setup_success_returns_paths(tmp_path, monkeypatch):
    # sahte ffmpeg + yt-dlp + deno zip ⇒ ToolPaths(bin/yt-dlp, bin/deno, bin/ffmpeg) ve st.ready True
def test_updater_rate_limit_and_hidden():
    now = [1000.0]; calls = []
    def run(args, **kw): calls.append((args, kw))
    u = tools.YtdlpUpdater(Path("/b/yt-dlp"), clock=lambda: now[0], run=run)
    assert u.trigger() is True; wait_until(lambda: not u.is_running)
    now[0] += 10; assert u.trigger() is False
    now[0] += 1800; assert u.trigger() is True; wait_until(lambda: not u.is_running)
    assert calls[0][0] == [str(Path("/b/yt-dlp")), "-U"]
    assert tools.hidden_subprocess_kwargs().items() <= calls[0][1].items()
```

- [ ] **Step 2: Çalıştır** → `python -m pytest tests/test_tools_setup.py -v` → Expected: FAIL (`AttributeError: ... 'ensure_ytdlp'`)
- [ ] **Step 3: Interfaces'teki öğeleri `backend/tools.py`'ye ekle**
- [ ] **Step 4: Çalıştır** → `python -m pytest tests -v` → Expected: tümü PASS
- [ ] **Step 5: Commit** → `git commit -am "masaustu: yt-dlp ve deno kurulumu, guncelleyici"` (yeni test dosyasını `git add` ile ekle)

---

### Task 4: `converter.py`'yi yerel kullanım için sadeleştir

**Files:**
- Modify: `backend/converter.py` (tamamen yeniden yazılır)
- Create: `tests/test_converter.py`

**Interfaces:**
- Consumes: `tools.ToolPaths`, `tools.hidden_subprocess_kwargs()`.
- Produces:
  - `configure(tool_paths: ToolPaths, jobs_dir: Path, on_blocked: Callable[[], None] = lambda: None) -> None`
  - `validate_url(url: str) -> bool`, `sanitize_title(t: str) -> str` (mevcut davranış korunur)
  - `base_args(tp: ToolPaths) -> list[str]` = `[str(tp.ytdlp), "--ignore-config", "--no-playlist", "--js-runtimes", f"deno:{tp.deno}", "--ffmpeg-location", str(tp.ffmpeg)]`
  - `info_cmd(tp, url) -> list[str]` = `base_args(tp) + ["--dump-json", url]`
  - `download_cmd(tp, url, output_tpl: str) -> list[str]` = `base_args(tp) + ["-x", "--audio-format", "mp3", "--audio-quality", "0", "--newline", "--progress-template", "download:PROGRESS %(progress._percent_str)s", "--output", output_tpl, url]`
  - `is_blocked(raw: str) -> bool` — `"403"`, `"forbidden"`, `"no video formats"`, `"sign in to confirm"` (küçük harf)
  - `friendly_error(raw: str) -> str` — engelde `BLOCKED_MSG`; `private` → `"Bu video gizli (private)."`;
    `unavailable`/`not available` → `"Video bulunamadı veya kaldırılmış."`; yaş → mevcut metin; diğerleri `raw[:300]`
  - `BLOCKED_MSG = "YouTube indirmeyi engelledi. yt-dlp güncelleniyor; birkaç dakika sonra tekrar dene."`
  - `start_job(url) -> dict` (= `_new_job(url)` + executor'a `_run_job`), `get_job(job_id) -> dict | None`,
    `active_job_count() -> int` (`queued`/`processing`), `build_download_response_path(job_id) -> tuple[Path | None, str | None]`,
    `sweep_expired() -> list[str]`, `start_janitor() -> None`
  - Test dikişleri: `_new_job(url) -> dict`, `_run_job(job, url) -> None`,
    `_run_info(cmd) -> subprocess.CompletedProcess` (timeout 60, hidden kwargs),
    `_popen_download(job, cmd) -> tuple[bool, str]` (mevcut ilerleme ayrıştırma + hidden kwargs).
- Çıkarılanlar: cookies, PO Token, Invidious, `FALLBACK_ARGS`, impersonate, proxy, `debug_info`,
  `resolve_ffmpeg`. Günlük: `logging.getLogger("mp3.converter")`.
- Engel durumunda `on_blocked()` çağrılır ve iş hatası `BLOCKED_MSG` olur.

- [ ] **Step 1: Başarısız testleri yaz**

```python
TP = ToolPaths(Path("/b/yt-dlp"), Path("/b/deno"), Path("/b/ffmpeg"))
def test_validate_url():
    for ok in ("https://youtu.be/jNQXAC9IVRw", "https://www.youtube.com/shorts/abcdefghijk",
               "https://music.youtube.com/watch?v=jNQXAC9IVRw"): assert converter.validate_url(ok)
    assert not converter.validate_url("https://vimeo.com/123456")
def test_info_cmd_uses_tool_paths():
    assert converter.info_cmd(TP, "U") == [str(TP.ytdlp), "--ignore-config", "--no-playlist",
        "--js-runtimes", f"deno:{TP.deno}", "--ffmpeg-location", str(TP.ffmpeg), "--dump-json", "U"]
def test_download_cmd_contains_mp3_flags():
    cmd = converter.download_cmd(TP, "U", "/j/%(id)s.%(ext)s")
    assert cmd[-1] == "U" and ["-x", "--audio-format", "mp3"] == cmd[7:10]
def test_friendly_error():
    assert converter.friendly_error("ERROR: [youtube] x: No video formats found!") == converter.BLOCKED_MSG
    assert converter.friendly_error("ERROR: Private video") == "Bu video gizli (private)."
def test_job_success_flow(tmp_path, monkeypatch):
    converter.configure(TP, tmp_path)
    monkeypatch.setattr(converter, "_run_info", lambda cmd: subprocess.CompletedProcess(cmd, 0, '{"title": "Şarkı / Test"}', ""))
    def fake_dl(job, cmd): (Path(job["dir"]) / "abc.mp3").write_bytes(b"ID3" + b"0" * 1000); return True, ""
    monkeypatch.setattr(converter, "_popen_download", fake_dl)
    job = converter._new_job("https://youtu.be/jNQXAC9IVRw"); converter._run_job(job, "https://youtu.be/jNQXAC9IVRw")
    assert job["status"] == "done" and job["filename"] == "Şarkı Test.mp3" and job["progress"] == 100
def test_job_blocked_calls_on_blocked(tmp_path, monkeypatch):
    calls = []; converter.configure(TP, tmp_path, on_blocked=lambda: calls.append(1))
    monkeypatch.setattr(converter, "_run_info", lambda cmd: subprocess.CompletedProcess(cmd, 1, "", "ERROR: [youtube] x: No video formats found!"))
    job = converter._new_job("U"); converter._run_job(job, "U")
    assert job["status"] == "error" and job["error"] == converter.BLOCKED_MSG and calls == [1]
def test_active_job_count(tmp_path):  # iki _new_job (queued), birini "done" yap ⇒ 1
def test_subprocesses_hidden(tmp_path, monkeypatch):
    # subprocess.run ve subprocess.Popen'ı kaydeden sahtelerle değiştir; _run_info ve _popen_download
    # çağrılarının kwargs'ı hidden_subprocess_kwargs()'ı içermeli
```

- [ ] **Step 2: Çalıştır** → `python -m pytest tests/test_converter.py -v` → Expected: FAIL
- [ ] **Step 3: `backend/converter.py`'yi Interfaces'e göre yeniden yaz**
- [ ] **Step 4: Çalıştır** → `python -m pytest tests -v` → Expected: tümü PASS
- [ ] **Step 5: Commit** → `git commit -am "masaustu: converter yerel kullanim icin sadelestirildi"` (+ yeni test dosyası)

---

### Task 5: `lifecycle.py` ve `instance.py`

**Files:**
- Create: `backend/lifecycle.py`, `backend/instance.py`, `tests/test_lifecycle.py`, `tests/test_instance.py`

**Interfaces:**
- Produces:
  - `class Lifecycle(clock=time.monotonic, grace: float = 120.0, idle_timeout: float = 180.0)`:
    `heartbeat() -> None`; `should_exit(active_jobs: int) -> bool` — iş varsa `False`; hiç
    heartbeat yoksa başlangıçtan `grace` geçince `True`; varsa son heartbeat'ten `idle_timeout` geçince `True`.
  - `instance.read_port(path: Path) -> int | None` (yok/bozuk → `None`),
    `instance.write_port(path: Path, port: int) -> None` (`{"port": port, "pid": os.getpid()}`),
    `instance.clear(path: Path, port: int) -> None` (yalnızca dosyadaki port eşleşirse siler),
    `instance.probe(port: int, timeout: float = 2.0, opener=urllib.request.urlopen) -> bool`
    (`http://127.0.0.1:{port}/api/health` JSON'unda `app == APP_ID`; her hata `False`),
    `instance.find_running(path: Path, probe=probe) -> int | None`.

- [ ] **Step 1: Başarısız testleri yaz**

```python
def test_no_exit_during_grace():
    t = [0.0]; lc = Lifecycle(clock=lambda: t[0])
    t[0] = 119; assert not lc.should_exit(0)
    t[0] = 121; assert lc.should_exit(0)
def test_background_tab_throttling_does_not_exit():
    t = [0.0]; lc = Lifecycle(clock=lambda: t[0])
    for beat in (0, 70, 140, 210):
        t[0] = beat; lc.heartbeat(); t[0] = beat + 69; assert not lc.should_exit(0)
def test_exit_after_idle_timeout():
    t = [10.0]; lc = Lifecycle(clock=lambda: t[0]); lc.heartbeat()
    t[0] = 189; assert not lc.should_exit(0)
    t[0] = 191; assert lc.should_exit(0)
def test_running_job_blocks_exit():
    t = [0.0]; lc = Lifecycle(clock=lambda: t[0]); t[0] = 1000; assert not lc.should_exit(1)
def test_instance_roundtrip_and_corrupt(tmp_path):
    f = tmp_path / "instance.json"; instance.write_port(f, 5123); assert instance.read_port(f) == 5123
    f.write_text("{bozuk"); assert instance.read_port(f) is None
def test_clear_keeps_other_instance(tmp_path):
    f = tmp_path / "instance.json"; instance.write_port(f, 1); instance.clear(f, 2); assert f.exists()
    instance.clear(f, 1); assert not f.exists()
def test_probe():
    assert instance.probe(1, opener=json_opener({"app": "mp3donusturucum"})) is True
    assert instance.probe(1, opener=json_opener({"app": "baska"})) is False
    assert instance.probe(1, opener=raising_opener) is False
def test_find_running_ignores_dead(tmp_path):
    f = tmp_path / "instance.json"; instance.write_port(f, 5123)
    assert instance.find_running(f, probe=lambda p: False) is None
    assert instance.find_running(f, probe=lambda p: True) == 5123
```

- [ ] **Step 2: Çalıştır** → `python -m pytest tests/test_lifecycle.py tests/test_instance.py -v` → Expected: FAIL
- [ ] **Step 3: İki modülü Interfaces'e göre yaz**
- [ ] **Step 4: Çalıştır** → Expected: tümü PASS
- [ ] **Step 5: Commit** → `git commit -m "masaustu: otomatik kapanma ve tek kopya kontrolu"`

---

### Task 6: `updates.py` ve yerel API (`app.py`)

**Files:**
- Create: `backend/updates.py`, `tests/test_updates.py`, `tests/test_app.py`
- Modify: `backend/app.py` (yeniden yazılır; `flask_cors` kaldırılır)

**Interfaces:**
- Consumes: `tools.SetupState`, `lifecycle.Lifecycle`, `converter.*`, `paths.resource_dir`, `paths.APP_ID`, `version.__version__`.
- Produces:
  - `updates.RELEASES_API = "https://api.github.com/repos/efebalci569-dot/mp3-donusturucu/releases/latest"`
  - `updates.parse_version(tag: str) -> tuple[int, ...] | None` — baştaki `v` atılır; `^\d+(\.\d+)*$` değilse `None`
  - `updates.check_latest(current: str, fetch: Callable[[str], dict] = _fetch_json) -> dict | None` —
    `current` ayrıştırılamıyorsa (ör. `0.0.0-dev`) `fetch` çağrılmadan `None`; `tag_name` daha yeniyse
    `{"available": True, "version": tag_name, "url": html_url}`; aksi/hata → `None`. `_fetch_json` timeout 10 sn,
    `User-Agent: MP3Donusturucum/<sürüm>`.
  - `app.create_app(port: int, setup: SetupState, lifecycle: Lifecycle, retry_setup: Callable[[], None], update_info: Callable[[], dict | None]) -> Flask`
    - `before_request`: `request.host` ∉ {`127.0.0.1:{port}`, `localhost:{port}`} → 403 `{"success": False, "error": "Yasak"}`
    - `GET /`, `GET /<path:asset>` → `resource_dir()/"frontend"`
    - `GET /api/health` → `{"status": "ok", "app": APP_ID, "version": __version__}`
    - `GET /api/setup` → `setup.to_dict() | {"update": update_info()}`
    - `POST /api/setup/retry` → `retry_setup()`; 202 `{"success": True}`
    - `POST /api/heartbeat` → `lifecycle.heartbeat()`; 204
    - `POST /api/convert` → kurulum hazır değilse 503 `{"success": False, "error": "Uygulama hâlâ hazırlanıyor, birazdan tekrar dene."}`; aksi halde mevcut doğrulama + 202 `{"success": True, "job_id": ...}`
    - `GET /api/status/<id>`, `GET /api/download/<id>` → mevcut davranış (`log` alanı çıkarılır)

- [ ] **Step 1: Başarısız testleri yaz**

```python
# test_updates.py
def test_newer_release():
    assert updates.check_latest("1.0.0", fetch=lambda u: {"tag_name": "v1.1.0", "html_url": "H"}) \
        == {"available": True, "version": "v1.1.0", "url": "H"}
def test_same_release(): assert updates.check_latest("1.1.0", fetch=lambda u: {"tag_name": "v1.1.0", "html_url": "H"}) is None
def test_dev_version_skips_fetch(): assert updates.check_latest("0.0.0-dev", fetch=boom) is None
def test_fetch_error(): assert updates.check_latest("1.0.0", fetch=boom) is None

# test_app.py — B = "http://127.0.0.1:5000"
# fixture client: create_app(5000, SetupState(), Lifecycle(), retry, lambda: None).test_client()  (kurulum hazır değil)
# fixture ready_client: aynısı, ama SetupState'in üç adımı "ready" ve converter.configure(TP, tmp_path) çağrılmış
def test_rejects_foreign_host(client):
    assert client.get("/api/health", base_url="http://evil.com:5000").status_code == 403
    assert client.get("/api/health", base_url=B).status_code == 200
def test_health_identifies_app(client): assert client.get("/api/health", base_url=B).json["app"] == "mp3donusturucum"
def test_index_served(client): assert "MP3 DÖNÜŞTÜRÜCÜM" in client.get("/", base_url=B).get_data(as_text=True)
def test_convert_while_setup_not_ready_returns_503(client):
    r = client.post("/api/convert", json={"url": "https://youtu.be/jNQXAC9IVRw"}, base_url=B); assert r.status_code == 503
def test_convert_rejects_non_json_body(ready_client):
    r = ready_client.post("/api/convert", data="url=https://youtu.be/jNQXAC9IVRw", content_type="text/plain", base_url=B)
    assert r.status_code == 400
def test_heartbeat_calls_lifecycle(...): # sahte lifecycle'ın heartbeat sayısı 1 olur; yanıt 204
def test_setup_includes_update(...):    # update_info → {"available": True, ...} ⇒ /api/setup json["update"]["available"] is True
def test_setup_retry_calls_callback(...): # 202 ve retry bir kez çağrıldı
def test_download_non_ascii_filename_header(ready_client, tmp_path, monkeypatch):
    f = tmp_path / "a.mp3"; f.write_bytes(b"ID3")
    monkeypatch.setattr(converter, "build_download_response_path", lambda j: (str(f), "Şarkı.mp3"))
    cd = ready_client.get("/api/download/x", base_url=B).headers["Content-Disposition"]
    assert "filename*=UTF-8''%C5%9Eark%C4%B1.mp3" in cd
```

- [ ] **Step 2: Çalıştır** → `python -m pytest tests/test_updates.py tests/test_app.py -v` → Expected: FAIL
- [ ] **Step 3: `updates.py`'yi yaz, `app.py`'yi `create_app` olarak yeniden yaz**
- [ ] **Step 4: Çalıştır** → `python -m pytest tests -v` → Expected: tümü PASS
- [ ] **Step 5: Commit** → `git commit -m "masaustu: yerel API, host kontrolu, surum bildirimi"`

---

### Task 7: `launcher.py` — giriş noktası

**Files:**
- Create: `backend/launcher.py`, `tests/test_launcher.py`

**Interfaces:**
- Consumes: Task 1–6'daki tüm modüller.
- Produces: `launcher.main(argv: list[str] | None = None) -> int`; bayraklar `--smoke-test`, `--no-browser`.
- Davranış:
  1. `_ensure_std_streams()` — `sys.stdout`/`sys.stderr` `None` ise `open(os.devnull, "w")`.
  2. Veri klasörü (`--smoke-test`'te `tempfile.mkdtemp()`), `bin/` ve `jobs/` oluşturulur; günlük
     `RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=1, encoding="utf-8")`.
  3. Normal modda `instance.find_running(...)` bir port verirse `webbrowser.open(f"http://127.0.0.1:{port}/")`, `return 0`.
  4. Boş port (`socket` ile `127.0.0.1:0`), `create_app(...)`, `werkzeug.serving.make_server("127.0.0.1", port, app, threaded=True)`;
     bağlanamazsa yeni portla bir kez daha dener.
  5. `--smoke-test`: `ensure_ffmpeg` + `[ffmpeg, "-version"]` (hidden kwargs) dönüş kodu 0; sunucu thread'de;
     `/api/health` `app == APP_ID`; sunucuyu kapatır; geçici klasörü siler; başarıda 0, aksi halde 1.
     Ağdan bir şey indirmez.
  6. Normal: `instance.write_port`; kurulum thread'i (`run_setup` → başarıda `converter.configure(paths, jobs_dir, on_blocked=updater.trigger)`
     ve `updater.trigger()`); güncelleme kontrolü thread'i (`updates.check_latest(__version__)` sonucu `update_info`'ya);
     `retry_setup` hata durumunda kurulum thread'ini yeniden başlatır; izleyici thread her 5 sn
     `lifecycle.should_exit(converter.active_job_count())` → `server.shutdown()`; `--no-browser` yoksa tarayıcı açılır;
     `serve_forever()`; `finally` içinde `instance.clear`. `converter.start_janitor()` çağrılır.

- [ ] **Step 1: Başarısız testleri yaz**

```python
def test_smoke_test_passes(): assert launcher.main(["--smoke-test"]) == 0
def test_smoke_test_with_none_streams(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None); monkeypatch.setattr(sys, "stderr", None)
    assert launcher.main(["--smoke-test"]) == 0
def test_second_instance_opens_browser(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(launcher.paths, "data_dir", lambda *a, **k: tmp_path)
    monkeypatch.setattr(launcher.instance, "find_running", lambda path, **k: 5123)
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    assert launcher.main([]) == 0 and opened == ["http://127.0.0.1:5123/"]
```

- [ ] **Step 2: Çalıştır** → `python -m pytest tests/test_launcher.py -v` → Expected: FAIL
- [ ] **Step 3: `backend/launcher.py`'yi yaz**
- [ ] **Step 4: Çalıştır** → `python -m pytest tests -v` → Expected: tümü PASS
- [ ] **Step 5: Commit** → `git commit -m "masaustu: launcher giris noktasi ve duman testi"`

---

### Task 8: Arayüz — kurulum ekranı, güncelleme şeridi, heartbeat

**Files:**
- Modify: `frontend/index.html`, `frontend/script.js`, `frontend/style.css`

**Interfaces:**
- Consumes: `GET /api/setup`, `POST /api/setup/retry`, `POST /api/heartbeat`, mevcut `convert/status/download`.

- [ ] **Step 1: `index.html`**: `.converter-card` içinde `.input-group`'tan önce
  `#setup.setup.hidden` (içinde `p.setup-title` "İlk kurulum: araçlar indiriliyor", `ul#setupSteps`,
  `p#setupError.setup-error.hidden`, `button#setupRetry.convert-btn.hidden` "Tekrar dene");
  `header`'dan önce `a#updateBanner.update-banner.hidden` (`target="_blank" rel="noopener"`).
- [ ] **Step 2: `script.js`**:
  - `setupReady` bayrağı; `pollSetup()` hazır olana kadar 1000 ms'de bir `/api/setup`; adım adları
    `{ffmpeg: "FFmpeg", ytdlp: "yt-dlp", deno: "Deno"}`, durum metinleri `pending` → "bekliyor",
    `downloading` → "%<progress>", `ready` → "hazır ✓", `error` → "hata". Hazır değilken `convertBtn.disabled = true`;
    `hideLoading()` düğmeyi yalnızca `setupReady` ise açar.
  - `error` varsa `#setupError` + `#setupRetry`; tıklanınca `POST /api/setup/retry`, sonra yoklamaya devam.
  - `update.available` ise şerit: ``Yeni sürüm var (${version}) — indirmek için tıkla``, `href = url`.
  - Heartbeat: açılışta bir kez ve `setInterval(..., 10000)` ile `POST /api/heartbeat` (hatalar yutulur).
  - `parseJsonSafe` hata metni: ``Uygulamadan beklenmeyen yanıt geldi (HTTP ${res.status}). Uygulamayı kapatıp yeniden açmayı dene.``
- [ ] **Step 3: `style.css`**: `.setup`, `.setup-steps`, `.setup-error`, `.update-banner` mevcut
  `--accent`, `--error`, `--bg-card`, `--border`, `--radius-sm` değişkenleriyle.
- [ ] **Step 4: Uçtan uca elle doğrulama (Windows, gerçek ağ)**

```bash
export LOCALAPPDATA="$(mktemp -d)"   # temiz ilk kurulum
python backend/launcher.py
```
Expected: tarayıcıda kurulum adımları ilerler → "hazır ✓" → düğme açılır →
`https://www.youtube.com/watch?v=jNQXAC9IVRw` dönüştürülür → indirilen dosya MP3
(ilk baytlar `ID3` veya `FF FB`). Sekmeyi kapat → en geç ~4 dk içinde süreç biter ve
`instance.json` silinir. İkinci açılışta araçlar yeniden inmez.
- [ ] **Step 5: Hata ekranını doğrula**: `HTTPS_PROXY=http://127.0.0.1:9` ile yeni bir temiz
  `LOCALAPPDATA`'da başlat → kurulum hatası ve "Tekrar dene" düğmesi görünür.
- [ ] **Step 6: Commit** → `git commit -am "masaustu: kurulum ekrani, guncelleme seridi, heartbeat"`

---

### Task 9: PyInstaller paketi ve Windows kurulum betiği

**Files:**
- Create: `packaging/mp3donusturucum.spec`, `packaging/smoke_test.py`, `packaging/windows/installer.iss`

**Interfaces:**
- Produces:
  - Spec: giriş `backend/launcher.py`, `pathex=["backend"]`, `datas=[("frontend", "frontend")] + collect_data_files("imageio_ffmpeg")`,
    `EXE(name="MP3Donusturucum", console=False, exclude_binaries=True)`, `COLLECT(name="MP3Donusturucum")`;
    macOS'ta ek olarak `BUNDLE(name="MP3Donusturucum.app", bundle_identifier="io.github.efebalci569.mp3donusturucum",
    info_plist={"LSUIElement": True, "CFBundleShortVersionString": <version.py'den>})`. Yollar spec dosyasının
    konumuna göre (`SPECPATH`) çözülür.
  - `packaging/smoke_test.py <çalıştırılabilir>`: `[exe, "--smoke-test"]` (timeout 180) dönüş kodunu
    döndürür, `SMOKE OK` / `SMOKE FAIL (<kod>)` yazar.
  - `installer.iss`: `AppName=MP3 Dönüştürücüm`, `AppVersion={#AppVersion}`,
    `DefaultDirName={localappdata}\Programs\MP3Donusturucum`, `PrivilegesRequired=lowest`,
    `OutputBaseFilename=MP3Donusturucum-Windows-Kurulum`, kaynak `dist\MP3Donusturucum\*` (recursesubdirs),
    Başlat menüsü kısayolu, işaretsiz gelen `desktopicon` görevi, kurulum sonunda çalıştırma
    (`postinstall nowait skipifsilent`), diller Türkçe + İngilizce.

- [ ] **Step 1: Paketi derle** → `pyinstaller packaging/mp3donusturucum.spec --noconfirm` →
  Expected: `dist/MP3Donusturucum/MP3Donusturucum.exe` oluşur.
- [ ] **Step 2: Duman testi** → `python packaging/smoke_test.py dist/MP3Donusturucum/MP3Donusturucum.exe` → Expected: `SMOKE OK`, çıkış 0.
- [ ] **Step 3: Paketlenmiş uygulamayla elle test** — temiz `LOCALAPPDATA` ile
  `dist/MP3Donusturucum/MP3Donusturucum.exe`'yi çift tıkla: konsol penceresi **yanıp sönmemeli**
  (kurulum ve dönüştürme sırasında da), Task 8 Step 4'teki akış aynen çalışmalı.
- [ ] **Step 4: (iscc varsa)** `iscc /DAppVersion=0.0.0 packaging/windows/installer.iss` → kurulum dosyası
  oluşur; yoksa bu adım CI'da doğrulanır (Task 10).
- [ ] **Step 5: Commit** → `git add packaging && git commit -m "masaustu: pyinstaller paketi ve windows kurulumu"`

---

### Task 10: GitHub Actions — test ve derleme/yayın

**Files:**
- Create: `.github/workflows/test.yml`, `.github/workflows/release.yml`

**Interfaces:**
- `test.yml`: `push` ve `pull_request`; matris `ubuntu-22.04`, `windows-latest`, `macos-15`; Python 3.12;
  bağımlılıkları kurar, `python -m pytest -q`.
- `release.yml`: tetikleyiciler `push: tags: ["v*"]` ve `pull_request` (PR'da yalnızca derler).
  - `build` matrisi (`include`): `windows-latest` → Windows-Kurulum.exe; `macos-15` → Mac-AppleSilicon.zip;
    `macos-15-intel` → Mac-Intel.zip; `ubuntu-22.04` → Linux-x64.tar.gz (adlar Global Constraints'teki gibi).
  - Adımlar: checkout → Python 3.12 → bağımlılıklar → sürüm yaz (etikette `${GITHUB_REF_NAME#v}`,
    PR'da `0.0.0-ci.${GITHUB_RUN_NUMBER}`) `backend/version.py`'ye → pytest → pyinstaller →
    `packaging/smoke_test.py` (Windows `dist/MP3Donusturucum/MP3Donusturucum.exe`, macOS
    `dist/MP3Donusturucum.app/Contents/MacOS/MP3Donusturucum`, Linux `dist/MP3Donusturucum/MP3Donusturucum`) →
    paketle (Windows: `choco install innosetup -y --no-progress` + `iscc /DAppVersion=...`;
    macOS: `ditto -c -k --keepParent dist/MP3Donusturucum.app <asset>`;
    Linux: `tar -czf <asset> -C dist MP3Donusturucum`) → `actions/upload-artifact` (ad = asset).
  - `release` işi: `needs: build`, `if: startsWith(github.ref, 'refs/tags/v')`, `permissions: contents: write`;
    artifact'ları indirir, `gh release create "$GITHUB_REF_NAME" <4 dosya> --title "MP3 Dönüştürücüm $GITHUB_REF_NAME" --generate-notes`.

- [ ] **Step 1: İki workflow dosyasını yaz**
- [ ] **Step 2: Kullanıcı onayıyla dalı push et ve PR aç** (`gh pr create --base main --head masaustu-uygulama`)
- [ ] **Step 3: Doğrula** → `gh pr checks` → Expected: `test` (3 OS) ve `build` (4 platform) yeşil;
  dört artifact mevcut (`gh run view <id> --json artifacts`).
- [ ] **Step 4: Windows artifact'ını indir**, kurulum dosyasıyla kur (yönetici izni istememeli),
  Başlat menüsünden aç, gerçek video dönüştür, kaldırıcıyla kaldır.
- [ ] **Step 5: Commit** (düzeltme gerekirse) ve push.

---

### Task 11: İndirme sitesi, eski sunucu dosyalarının temizliği, README

**Files:**
- Create: `site/index.html`, `site/style.css`, `site/script.js`
- Modify: `vercel.json`, `README.md`, `.vscode/launch.json` (program → `backend/launcher.py`)
- Delete: `api/proxy.py`, `api/requirements.txt`, `backend/Dockerfile`, `backend/start.sh`, `calistir.bat`, `cookies_temizle.bat`

**Interfaces:**
- `RELEASE_BASE = "https://github.com/efebalci569-dot/mp3-donusturucu/releases/latest/download/"`
- `site/script.js`: `detectOS() -> "windows" | "mac" | "linux" | "other"` (`navigator.userAgentData?.platform`,
  yoksa `navigator.userAgent`); Android/iOS → `"other"`. Ana düğme algılanan sisteme göre; Mac'te iki düğme
  ("Apple Silicon (M1–M4)" / "Intel", ipucu: "Apple menüsü → Bu Mac Hakkında → Çip"); `"other"`'da
  "Bu uygulama bilgisayarlar içindir" + tüm platform listesi. Altta her zaman tüm platformlar listesi.
- İlk açılış rehberi metinleri spec §5'teki gibi (Windows SmartScreen, macOS Sistem Ayarları → Gizlilik ve
  Güvenlik → "Yine de Aç", Linux arşivi açıp çalıştırma). YouTube kullanım şartları notu altta.
- `vercel.json` → `{"$schema": "https://openapi.vercel.sh/vercel.json", "outputDirectory": "site", "cleanUrls": true}`
- README: yeni mimari, geliştirme (`py -3.11 -m venv .venv`, kurulum, `python backend/launcher.py`,
  `python -m pytest`), yayın (`git tag v1.0.0 && git push origin v1.0.0`), YouTube notu.

- [ ] **Step 1: `site/` dosyalarını yaz** (görünüm `frontend/style.css` değişkenleriyle aynı aile)
- [ ] **Step 2: Siteyi tarayıcı panelinde doğrula** — `python -m http.server 8080 -d site` →
  masaüstünde Windows düğmesi öne çıkar, dört bağlantı `RELEASE_BASE + <asset>`; `mobile` önayarında
  "Bu uygulama bilgisayarlar içindir" görünür; yatay kaydırma yok.
- [ ] **Step 3: Eski dosyaları sil, `vercel.json`, README ve `.vscode/launch.json`'ı güncelle**
- [ ] **Step 4: Tüm testler** → `python -m pytest -q` → Expected: tümü PASS
- [ ] **Step 5: Commit** → `git commit -am "masaustu: indirme sitesi, sunucu dosyalari kaldirildi"` (+ yeni/silinen dosyalar) ve push (PR güncellenir).

---

### Task 12: Yayın (her adım kullanıcı onayıyla)

- [ ] **Step 1:** PR'daki tüm kontroller yeşil ve Task 10 Step 4 tamam.
- [ ] **Step 2:** PR başını etiketle: `git tag v1.0.0 && git push origin v1.0.0` →
  Expected: `release.yml` dört dosyayla `v1.0.0` Release'ini oluşturur
  (`gh release view v1.0.0 --json assets --jq '.assets[].name'`).
- [ ] **Step 3:** PR'ı birleştir (`gh pr merge --merge`) → Vercel `site/`'ı yayınlar.
- [ ] **Step 4:** Canlı doğrulama: `https://mp3-donusturucu.vercel.app` açılır; dört bağlantı için
  `curl -sI <RELEASE_BASE><asset>` → `302`.
- [ ] **Step 5:** Vercel'deki `BACKEND_URL` ortam değişkenini kaldır (kullanıcı onayıyla, Chrome'dan).
- [ ] **Step 6:** Kullanıcıya bildir: macOS ve Linux'ta gerçek indirme testi için o sistemleri kullanan
  birinin denemesi gerekiyor.

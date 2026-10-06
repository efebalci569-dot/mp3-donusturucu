const RELEASE_BASE = 'https://github.com/efebalci569-dot/mp3-donusturucu/releases/latest/download/';

const DOWNLOADS = {
    windows: [{ label: 'Windows için indir', asset: 'MP3Donusturucum-Windows-Kurulum.exe', icon: 'fab fa-windows' }],
    mac: [
        { label: 'Apple Silicon (M1–M4)', asset: 'MP3Donusturucum-Mac-AppleSilicon.zip', icon: 'fab fa-apple' },
        { label: 'Intel', asset: 'MP3Donusturucum-Mac-Intel.zip', icon: 'fab fa-apple' },
    ],
    linux: [{ label: 'Linux (x64) için indir', asset: 'MP3Donusturucum-Linux-x64.tar.gz', icon: 'fab fa-linux' }],
};

const OS_NAMES = { windows: 'Windows', mac: 'macOS', linux: 'Linux' };

function detectOS() {
    const ua = navigator.userAgent || '';
    const data = navigator.userAgentData;
    const platform = (data && data.platform) || navigator.platform || '';
    if ((data && data.mobile) || /Android|iPhone|iPad|iPod/i.test(ua)) return 'other';
    if (/Win/i.test(platform) || /Windows/i.test(ua)) return 'windows';
    if (/Mac/i.test(platform) || /Mac OS X/i.test(ua)) {
        // iPadOS kendini Mac olarak tanıtır; dokunmatik ekran onu ele verir.
        return navigator.maxTouchPoints > 1 ? 'other' : 'mac';
    }
    if (/Linux|X11/i.test(platform + ua)) return 'linux';
    return 'other';
}

function downloadLink(item, className) {
    const a = document.createElement('a');
    a.className = className;
    a.href = RELEASE_BASE + item.asset;
    const icon = document.createElement('i');
    icon.className = item.icon;
    const text = document.createElement('span');
    text.textContent = item.label;
    a.append(icon, text);
    return a;
}

function render() {
    const os = detectOS();
    const primary = document.getElementById('primary');
    const hint = document.getElementById('primaryHint');
    const label = document.getElementById('detectedLabel');

    if (os === 'other') {
        label.textContent = 'Bu uygulama bilgisayarlar içindir';
        const p = document.createElement('p');
        p.className = 'other-note';
        p.textContent = 'MP3 Dönüştürücüm Windows, macOS ve Linux bilgisayarlarda çalışır. '
            + 'Bilgisayarından bu sayfayı açıp indirebilirsin.';
        primary.append(p);
    } else {
        label.textContent = `${OS_NAMES[os]} için indir`;
        DOWNLOADS[os].forEach(item => primary.append(downloadLink(item, 'download-btn')));
        if (os === 'mac') {
            hint.textContent = 'Hangisi olduğunu bilmiyorsan: Apple menüsü → Bu Mac Hakkında → Çip. '
                + '"Apple M…" yazıyorsa Apple Silicon, "Intel" yazıyorsa Intel.';
            hint.classList.remove('hidden');
        }
        const guide = document.getElementById(`guide-${os}`);
        if (guide) guide.open = true;
    }

    const all = document.getElementById('allPlatforms');
    Object.entries(DOWNLOADS).forEach(([key, items]) => {
        items.forEach(item => {
            const li = document.createElement('li');
            const name = key === 'mac' ? `macOS — ${item.label}` : OS_NAMES[key];
            li.append(downloadLink({ ...item, label: name }, 'platform-link'));
            all.append(li);
        });
    });
}

render();

const urlInput = document.getElementById('urlInput');
const convertBtn = document.getElementById('convertBtn');
const loading = document.getElementById('loading');
const progressText = document.getElementById('progressText');
const progressFill = document.getElementById('progressFill');
const error = document.getElementById('error');
const errorMessage = document.getElementById('errorMessage');
const result = document.getElementById('result');
const resultTitle = document.getElementById('resultTitle');
const resultSize = document.getElementById('resultSize');
const downloadBtn = document.getElementById('downloadBtn');
const setupBox = document.getElementById('setup');
const setupSteps = document.getElementById('setupSteps');
const setupError = document.getElementById('setupError');
const setupRetry = document.getElementById('setupRetry');
const updateBanner = document.getElementById('updateBanner');

const STEP_LABELS = { ffmpeg: 'FFmpeg', ytdlp: 'yt-dlp', deno: 'Deno' };
const NOT_READY_MSG = 'Uygulama hâlâ hazırlanıyor, birazdan tekrar dene.';

let pollTimer = null;
let setupReady = false;

function setProgress(pct) {
    progressText.textContent = `%${pct}`;
    progressFill.style.width = `${pct}%`;
}

function showLoading() {
    loading.classList.remove('hidden');
    error.classList.add('hidden');
    result.classList.add('hidden');
    setProgress(0);
    convertBtn.disabled = true;
    convertBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Dönüştürülüyor...</span>';
}

function hideLoading() {
    loading.classList.add('hidden');
    convertBtn.disabled = !setupReady;
    convertBtn.innerHTML = '<i class="fas fa-download"></i><span>İndir & Dönüştür</span>';
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

function showError(msg) {
    error.classList.remove('hidden');
    errorMessage.textContent = msg;
    result.classList.add('hidden');
    hideLoading();
}

function showSuccess(title, size, url) {
    result.classList.remove('hidden');
    resultTitle.textContent = title;
    resultSize.textContent = `${size.toFixed(1)} MB`;
    downloadBtn.href = url;
    hideLoading();
}

async function parseJsonSafe(res) {
    const text = await res.text();
    if (!text) {
        throw new Error(`Sunucu boş yanıt döndü (HTTP ${res.status})`);
    }
    try {
        return JSON.parse(text);
    } catch {
        throw new Error(
            `Uygulamadan beklenmeyen yanıt geldi (HTTP ${res.status}). ` +
            `Uygulamayı kapatıp yeniden açmayı dene.`
        );
    }
}

async function pollStatus(jobId) {
    try {
        const res = await fetch(`/api/status/${jobId}`);
        const data = await parseJsonSafe(res);

        if (!data.success) {
            showError(data.error || 'İş durumu alınamadı');
            return;
        }

        if (data.status === 'processing' && data.progress > 0) {
            setProgress(data.progress);
            return;
        }

        if (data.status === 'done') {
            showSuccess(data.title, data.size_mb, `/api/download/${jobId}`);
            urlInput.value = '';
            return;
        }

        if (data.status === 'error') {
            showError(data.error || 'Dönüştürme başarısız oldu');
        }
    } catch (e) {
        showError(e.message || 'Sunucuya bağlanılamadı. Lütfen tekrar deneyin.');
    }
}

async function convertUrl() {
    const url = urlInput.value.trim();

    if (!setupReady) {
        showError(NOT_READY_MSG);
        return;
    }

    if (!url) {
        showError('Lütfen bir YouTube linki girin');
        urlInput.focus();
        return;
    }

    const pattern = /^https?:\/\/(www\.|music\.|m\.)?(youtube\.com\/.+|youtu\.be\/.+)/;
    if (!pattern.test(url)) {
        showError('Geçerli bir YouTube linki girin (youtube.com veya youtu.be)');
        urlInput.focus();
        return;
    }

    showLoading();

    try {
        const res = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await parseJsonSafe(res);

        if (!data.success) {
            showError(data.error);
            return;
        }

        setProgress(1);
        pollTimer = setInterval(() => pollStatus(data.job_id), 2000);
        pollStatus(data.job_id);
    } catch (e) {
        showError(e.message || 'Sunucuya bağlanılamadı. Lütfen tekrar deneyin.');
    }
}

convertBtn.addEventListener('click', convertUrl);

urlInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
        e.preventDefault();
        convertUrl();
    }
});

urlInput.addEventListener('input', () => {
    if (!error.classList.contains('hidden')) error.classList.add('hidden');
});

function stepText(step) {
    if (step.state === 'ready') return 'hazır ✓';
    if (step.state === 'downloading') return `%${step.progress}`;
    if (step.state === 'error') return 'hata';
    return 'bekliyor';
}

function renderSetup(data) {
    // Sabit sıra: JSON anahtarları alfabetik gelir.
    const names = Object.keys(STEP_LABELS).filter(n => data.steps[n]);
    setupSteps.replaceChildren(...names.map(name => {
        const step = data.steps[name];
        const li = document.createElement('li');
        li.className = step.state;
        const label = document.createElement('span');
        label.textContent = STEP_LABELS[name] || name;
        const state = document.createElement('span');
        state.textContent = stepText(step);
        li.append(label, state);
        return li;
    }));

    setupError.textContent = data.error || '';
    setupError.classList.toggle('hidden', !data.error);
    setupRetry.classList.toggle('hidden', !data.error);

    if (data.update && data.update.available) {
        updateBanner.textContent = `Yeni sürüm var (${data.update.version}) — indirmek için tıkla`;
        updateBanner.href = data.update.url;
        updateBanner.classList.remove('hidden');
    }

    setupReady = data.ready;
    setupBox.classList.toggle('hidden', data.ready);
    if (loading.classList.contains('hidden')) convertBtn.disabled = !setupReady;
}

async function pollSetup() {
    try {
        const res = await fetch('/api/setup');
        const data = await parseJsonSafe(res);
        renderSetup(data);
        if (data.ready) {
            // Hazır olduktan sonra güncelleme bilgisi geç gelebilir; bir süre daha seyrek sor.
            setTimeout(pollUpdateOnce, 15000);
            return;
        }
        if (data.error) return;
    } catch {
        // Uygulama henüz yanıt vermiyor olabilir; tekrar dene.
    }
    setTimeout(pollSetup, 1000);
}

async function pollUpdateOnce() {
    try {
        const res = await fetch('/api/setup');
        renderSetup(await parseJsonSafe(res));
    } catch {
        // önemli değil
    }
}

setupRetry.addEventListener('click', async () => {
    setupRetry.classList.add('hidden');
    setupError.classList.add('hidden');
    try {
        await fetch('/api/setup/retry', { method: 'POST' });
    } catch {
        // pollSetup hatayı yeniden gösterecek
    }
    setTimeout(pollSetup, 500);
});

function heartbeat() {
    fetch('/api/heartbeat', { method: 'POST' }).catch(() => {});
}

convertBtn.disabled = true;
heartbeat();
setInterval(heartbeat, 10000);
pollSetup();

urlInput.focus();

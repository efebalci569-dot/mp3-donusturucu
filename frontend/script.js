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

let pollTimer = null;
let pollAttempts = 0;
const MAX_POLL_ATTEMPTS = 180;

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
    convertBtn.disabled = false;
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

async function pollStatus(jobId) {
    pollAttempts += 1;
    try {
        const res = await fetch(`/api/status/${jobId}`, { cache: 'no-store' });
        const raw = await res.text();
        let data;
        try {
            data = JSON.parse(raw);
        } catch {
            throw new Error(`Sunucu geçersiz yanıt verdi (HTTP ${res.status})`);
        }

        if (!res.ok || !data.success) {
            if (res.status >= 500 && pollAttempts < MAX_POLL_ATTEMPTS) return;
            showError(data.error || 'İş durumu alınamadı');
            return;
        }

        if (data.status === 'processing' || data.status === 'queued') {
            if (data.progress > 0) setProgress(data.progress);
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
    } catch (err) {
        if (pollAttempts < MAX_POLL_ATTEMPTS) {
            progressText.textContent = 'Sunucu uyanıyor, tekrar deneniyor...';
            return;
        }
        showError(err.message || 'Sunucuya bağlanılamadı. Lütfen tekrar deneyin.');
    }
}

async function convertUrl() {
    const url = urlInput.value.trim();

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
    pollAttempts = 0;

    try {
        const res = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await res.json();

        if (!res.ok || !data.success) {
            showError(data.error || `Sunucu hatası (HTTP ${res.status})`);
            return;
        }

        setProgress(1);
        pollTimer = setInterval(() => pollStatus(data.job_id), 2000);
        pollStatus(data.job_id);
    } catch (err) {
        showError(err.message || 'Sunucuya bağlanılamadı. Lütfen tekrar deneyin.');
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

urlInput.focus();

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
    try {
        const res = await fetch(`/api/status/${jobId}`);
        const data = await res.json();

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
    } catch {
        showError('Sunucuya bağlanılamadı. Lütfen tekrar deneyin.');
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

    try {
        const res = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await res.json();

        if (!data.success) {
            showError(data.error);
            return;
        }

        setProgress(1);
        pollTimer = setInterval(() => pollStatus(data.job_id), 2000);
        pollStatus(data.job_id);
    } catch {
        showError('Sunucuya bağlanılamadı. Lütfen tekrar deneyin.');
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

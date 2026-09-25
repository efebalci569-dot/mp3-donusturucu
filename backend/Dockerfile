FROM python:3.12-slim

# Node.js 22 (bgutil POT sunucusu için zorunlu) + ffmpeg + git
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg nodejs git \
    && rm -rf /var/lib/apt/lists/*

# PO Token üretici sunucu (plugin 2.0.0 ile eşleşen sürüm)
RUN git clone --single-branch --branch 2.0.0 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil \
    && cd /opt/bgutil/server && npm ci && npx tsc

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

ENV PORT=8000 \
    MAX_CONCURRENT_JOBS=2 \
    JOB_TTL_SECONDS=1800 \
    DOWNLOAD_TIMEOUT_SECONDS=600

EXPOSE 8000

CMD ["sh", "start.sh"]

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000 \
    MAX_CONCURRENT_JOBS=2 \
    JOB_TTL_SECONDS=1800 \
    DOWNLOAD_TIMEOUT_SECONDS=600

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:$PORT --timeout 900 --workers 1 --threads 4 app:app

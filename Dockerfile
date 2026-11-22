# Naukari Pakki study-notes renderer. Free host: Hugging Face Spaces (Docker, port 7860). Also works on Render, Fly.io, Cloud Run, a VPS.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium poppler-utils fonts-noto-core fonts-noto-ui-core fontconfig \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_BIN=/usr/bin/chromium MAX_JOBS=1 PORT=7860 RENDER_TMP=/tmp
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py render.py logo.png ./
# RENDER_SECRET must be set in the host's environment settings (same value as RENDER_SECRET in the bot's config.php)
CMD gunicorn -w 1 --threads 4 -t 180 -b 0.0.0.0:${PORT:-8080} app:app

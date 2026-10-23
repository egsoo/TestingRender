# Container for Telegram Bot with hot-reload supervisor
FROM python:3.12-slim

# Install system dependencies (ffmpeg is needed for media utilities)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

WORKDIR /app

# Clone the bot repository to pre-install dependencies at build time
ARG REPO_URL=https://github.com/yshalsager/telegram-utils-bot
RUN git clone --depth 1 "$REPO_URL" /app && uv pip install --system -r pyproject.toml || true

# Copy supervisor script
COPY runner.py /runner.py

ENV PYTHONUNBUFFERED=1 APP_DIR=/app
CMD ["python", "/runner.py"]

# Render worker/web image for telegram-utils-bot with instant hot-reload.
# Dependencies are installed at build time from your GitHub repo; code itself
# is pulled live from the Bot Panel by runner.py.
FROM python:3.14-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git build-essential pkg-config && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
ARG REPO_URL=https://github.com/yshalsager/telegram-utils-bot
RUN git clone --depth 1 "$REPO_URL" /app
# Match the bot's Python constraint and locked runtime dependencies. Any error
# fails the image build instead of launching a bot with missing libraries.
RUN uv sync --frozen --no-install-project --no-dev && .venv/bin/python -c "import orjson"
COPY runner.py /runner.py
ENV PYTHONUNBUFFERED=1 APP_DIR=/app PATH="/app/.venv/bin:$PATH"
CMD ["python", "/runner.py"]

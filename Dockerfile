FROM python:3.12-slim

WORKDIR /app

ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g; s|security.debian.org/debian-security|mirrors.cloud.tencent.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g; s|security.debian.org/debian-security|mirrors.cloud.tencent.com/debian-security|g' /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends gcc vim fonts-wqy-zenhei; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt && \
    PLAYWRIGHT_DOWNLOAD_HOST="${PLAYWRIGHT_DOWNLOAD_HOST}" python -m playwright install --with-deps chromium

COPY . .

RUN mkdir -p log data/chat_ai data/md

ENV LOCALSTORE_USE_CWD=true

EXPOSE 8080

CMD ["python", "bot.py"]

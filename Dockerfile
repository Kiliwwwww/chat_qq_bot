FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p log data/chat_ai data/md

ENV LOCALSTORE_USE_CWD=true

EXPOSE 8080

CMD ["python", "bot.py"]

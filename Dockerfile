FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080 HOST=0.0.0.0
ENV MESSAGES_BASE_URL="https://november7-730026606190.europe-west1.run.app" PAGE_SIZE=100 MAX_PAGES=10
CMD exec uvicorn app.main:app --host ${HOST} --port ${PORT}

FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .
RUN npm run build

FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    SERVE_FRONTEND=true \
    FRONTEND_DIST_DIR=/app/dist

# Build wheels from pinned requirements and keep the image small at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY gateway/requirements.txt /app/gateway/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /app/gateway/requirements.txt \
    && pip install --no-cache-dir 'google-auth>=2.29.0' 'requests>=2.31.0'

COPY gateway /app/gateway
COPY --from=frontend-build /app/dist /app/dist

RUN mkdir -p /app/data \
    && adduser --disabled-password --gecos '' --uid 1001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers ${WEB_CONCURRENCY:-1}"]

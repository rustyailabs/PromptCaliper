FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (gcc for compiled extensions, libpq-dev for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# --require-hashes ensures every package matches its pinned SHA-256 checksum.
# Tampered or substituted packages are rejected at install time.
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Copy gateway source into /app/gateway/ so the Python import path resolves correctly.
# Running `uvicorn gateway.main:app` from /app requires /app/gateway/__init__.py to exist.
COPY . /app/gateway/

# Create data directory for SQLite (dev) and run as non-root for least-privilege
RUN mkdir -p /app/data \
    && adduser --disabled-password --gecos '' --uid 1001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

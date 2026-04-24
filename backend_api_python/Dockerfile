# QuantDinger Backend API Dockerfile
# BASE_IMAGE can be overridden from docker-compose/.env.
ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE}

# Optional mainland mirrors (set via docker-compose build args from project-root .env)
ARG USE_CN_MIRROR=0
ARG PIP_INDEX_URL=

# Set working directory
WORKDIR /app

# Debian apt: optional Aliyun mirror, else bump deb.debian.org to HTTPS.
# Keeps image lean: only minimal build deps, then purge after pip.
RUN set -eux; \
    if [ "$USE_CN_MIRROR" = "1" ] && [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i -E \
        's|https?://deb.debian.org|https://mirrors.aliyun.com|g; s|https?://security.debian.org|https://mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources; \
    else \
      sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends --fix-missing \
    ca-certificates \
    curl \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file
COPY requirements.txt .

# Install Python dependencies (optional PyPI mirror via PIP_INDEX_URL)
RUN if [ -n "$PIP_INDEX_URL" ]; then \
      pip install --no-cache-dir --prefer-binary --timeout 180 -i "$PIP_INDEX_URL" -r requirements.txt; \
    else \
      pip install --no-cache-dir --prefer-binary --timeout 180 -r requirements.txt; \
    fi \
    # Remove build deps to keep image small
    && apt-get purge -y --auto-remove build-essential python3-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# Create log and data directories
RUN mkdir -p logs data/memory

# Expose port
EXPOSE 5000

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHON_API_HOST=0.0.0.0
ENV PYTHON_API_PORT=5000

# Use entrypoint script to check SECRET_KEY before starting
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Start command (gunicorn for production; override with CMD ["python", "run.py"] for dev)
CMD ["gunicorn", "-c", "gunicorn_config.py", "run:app"]

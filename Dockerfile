# Multi-stage build (simple for now, can be optimized further if needed)
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install minimal system dependencies (curl for optional diagnostics)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifest and install first (layer cache friendliness)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY ddns/ ddns/
COPY pyproject.toml README.md ./

# Create non-root user
RUN useradd -r -u 1001 appuser && chown -R appuser /app
USER appuser

# Set a sensible default locale (optional)
ENV LC_ALL=C.UTF-8 LANG=C.UTF-8

# Default entrypoint runs the updater; further args appended as CLI flags
ENTRYPOINT ["python", "-m", "ddns"]
# Default command: verbose single run. Override with e.g. --interval 300 or --once
CMD ["--verbose"]

# Example builds / runs (also in README):
# docker build -t cf-ddns .
# docker run --rm --env-file .env cf-ddns
# docker run --rm --env-file .env cf-ddns --once --verbose


# =============================================================================
# Multi-Stage Dockerfile — Cloud-Native ML Inference Platform
# =============================================================================
# Stage 1: Builder — install deps, train model
# Stage 2: Runtime — slim image, non-root user, production-ready
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy application code and train model
COPY app/ ./app/
RUN PYTHONPATH=/install/lib/python3.12/site-packages python -m app.train

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL maintainer="jyothiram266"
LABEL description="Cloud-Native ML Inference Platform"
LABEL version="1.0.0"

# Security: create non-root user
RUN groupadd -r mluser && useradd -r -g mluser -d /app -s /sbin/nologin mluser

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/

# Copy trained model artifact
COPY --from=builder /app/models/ ./models/

# Set ownership and switch to non-root user
RUN chown -R mluser:mluser /app
USER mluser

# Environment
ENV MODEL_PATH=/app/models/model.joblib
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
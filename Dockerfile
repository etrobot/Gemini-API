# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SETUPTOOLS_SCM_PRETEND_VERSION=1.0.0 \
    GEMINI_COOKIE_PATH=/tmp/gemini_cookies

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install uv

# Copy all project files first
COPY . .

# Install project dependencies
RUN uv pip install --system -e .

# Create a non-root user and ensure proper permissions
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /tmp/gemini_cookies && \
    chown -R appuser:appuser /tmp/gemini_cookies && \
    chmod 755 /tmp/gemini_cookies
USER appuser

# Expose port
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - run FastAPI server
CMD ["python", "-m", "uvicorn", "gemini_webapi.server:app", "--host", "0.0.0.0", "--port", "8000"]

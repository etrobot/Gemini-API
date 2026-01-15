# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
COPY tests/ ./tests/
COPY assets/ ./assets/
COPY .git/ ./.git/

# Install uv for faster dependency management
RUN pip install uv

# Install project dependencies (setuptools_scm needs git history)
RUN uv pip install --system -e .

# Install test dependencies
RUN uv pip install --system pytest pytest-asyncio

# Create a non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Default command - run tests
CMD ["python", "-m", "pytest", "tests/", "-v"]

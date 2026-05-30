FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install uv from the official image for 10x faster builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies using uv
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Create logs, data, and database directories
RUN mkdir -p logs data database

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:7860/api/v1/health')" || exit 1

# Run application
CMD ["python", "app.py"]

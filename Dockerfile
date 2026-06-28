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

# NLP now runs via OpenRouter API (google/gemini-2.5-flash:free)
# No local models — transformers/sentence-transformers removed from requirements.txt
# No pre-download step needed. Cold start: ~5s instead of ~45s.

# Copy application code
COPY . .

# Create logs, data, and database directories
RUN mkdir -p logs data database

# Expose port (HF Spaces uses 7860)
EXPOSE 7860



# Run application
CMD ["python", "app.py"]

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

ENV HF_HOME=/app/.cache
ENV HF_HUB_ENABLE_HF_TRANSFER=1
RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; AutoTokenizer.from_pretrained('cardiffnlp/twitter-roberta-base-sentiment-latest'); AutoModelForSequenceClassification.from_pretrained('cardiffnlp/twitter-roberta-base-sentiment-latest'); from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"
RUN chmod -R 777 /app/.cache
RUN python -c "import nltk; [nltk.download(res, download_dir='/usr/local/share/nltk_data', quiet=True) for res in ['punkt_tab', 'stopwords', 'brown', 'wordnet']]"

# Copy application code
COPY . .

# Create logs, data, and database directories
RUN mkdir -p logs data database

# Expose port (HF Spaces uses 7860)
EXPOSE 7860



# Run application
CMD ["python", "app.py"]

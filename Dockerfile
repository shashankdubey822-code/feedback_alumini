# Use official Python 3.11 image
FROM python:3.11-slim

# Set working directory to /app
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download required NLTK data using python -c
RUN python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords')"

# Copy the rest of the application code
COPY . .

# Expose port (Hugging Face Spaces uses 7860 by default)
EXPOSE 7860

# Command to run the application using Gunicorn (or you can use python app.py)
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]

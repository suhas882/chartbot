# Multi-stage / Lightweight Production Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV USE_TF=0
ENV TF_ENABLE_ONEDNN_OPTS=0

WORKDIR /app

# Install system dependencies needed for compiling certain packages (pdf, sqlite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and assets
COPY app/ ./app/
COPY frontend/ ./frontend/
COPY init_event_db.py .
COPY ingest_samples.py .

# Create data directories
RUN mkdir -p data/raw_documents data/chroma_data data/reports

# Initialize database and seed sample events
RUN python init_event_db.py

# Expose FastAPI application port
EXPOSE 8000

# Run FastAPI via Uvicorn in production mode
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

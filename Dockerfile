# Universal Multi-Platform Production Dockerfile
# Compatible with: Hugging Face Spaces (16GB RAM Free), Railway, Koyeb, Render, and Local Docker
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV USE_TF=0
ENV TF_ENABLE_ONEDNN_OPTS=0
ENV PORT=7860

WORKDIR /app

# Install system dependencies
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
COPY add_event.py .
COPY init_event_db.py .
COPY ingest_samples.py .

# Create data directories and set permissions for non-root container runners (UID 1000 on HF Spaces)
RUN mkdir -p data/raw_documents data/chroma_data data/reports && \
    chmod -R 777 /app/data

# Initialize database and seed sample events
RUN python init_event_db.py && \
    chmod 777 data/events.db

# Expose ports for HF Spaces (7860) and generic services (8000)
EXPOSE 7860
EXPOSE 8000

# Start Uvicorn respecting dynamic environment PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]

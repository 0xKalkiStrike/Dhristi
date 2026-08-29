FROM python:3.11-slim

# System libraries required by OpenCV / video decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# App code + helper scripts
COPY backend /app/backend
COPY scripts /app/scripts

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

EXPOSE 8000

# Initialise schema then serve
CMD ["sh", "-c", "python /app/scripts/setup/init_db.py && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]

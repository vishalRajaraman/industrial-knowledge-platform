FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm || true

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/ontology /app/data /tmp/uploads

# Cohere embedding is cloud API — no model weights to pre-download
# spaCy model download handles NER offline capability

ENV PORT=9090
EXPOSE 9090

CMD ["python", "server.py"]

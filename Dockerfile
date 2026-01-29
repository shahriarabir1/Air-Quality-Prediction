# Use official Python image with slim variant for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for TensorFlow and other libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libhdf5-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY index.html .
COPY map.html .
COPY map_chittagong.html .

# Copy model artifacts
COPY saved_models2/ ./saved_models2/
COPY artifacts_aqi_model_gpu_2_PM_NO/ ./artifacts_aqi_model_gpu_2_PM_NO/

# Create state_store directory
RUN mkdir -p state_store

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/simple')" || exit 1

# Run the application with dynamic port support
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}

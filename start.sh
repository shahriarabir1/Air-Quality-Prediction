#!/bin/bash
# Production startup script for AQ Forecast API

# Exit on error
set -e

# Set default port if not provided
PORT=${PORT:-8000}

echo "Starting AQ Forecast API on port $PORT..."

# Start uvicorn with production settings
exec uvicorn app:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 2 \
    --log-level info \
    --access-log \
    --no-use-colors

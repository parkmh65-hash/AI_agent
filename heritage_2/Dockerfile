FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Cloud Run passes PORT env var, default 8080)
ENV PORT=8080
EXPOSE 8080

# Run uvicorn server
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}

# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV HF_HOME=/app/hf_cache
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1

# Set work directory
WORKDIR /app

# Install system build dependencies (required for some compiled python dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from the Server directory
COPY Server/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download and cache CLIP model during build to prevent startup timeouts and HF rate limits
RUN python -c "from transformers import CLIPProcessor, CLIPModel; CLIPModel.from_pretrained('openai/clip-vit-base-patch32'); CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')"

# Copy source code files from the Server directory
COPY Server/ .

# Expose port
EXPOSE 8080

# Run uvicorn server, using 'exec' to handle process signals correctly on Cloud Run
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT

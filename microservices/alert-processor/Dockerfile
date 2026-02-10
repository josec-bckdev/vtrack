FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy shared package
COPY shared-package /app/shared-package

# Install shared package
RUN pip install --no-cache-dir /app/shared-package

# Copy alert processor
COPY microservices/alert-processor /app

# Install requirements
RUN pip install --no-cache-dir \
    redis \
    rq \
    geopy

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV REDIS_URL=redis://redis:6379/0

# Run the alert consumer
CMD ["python", "main.py"]

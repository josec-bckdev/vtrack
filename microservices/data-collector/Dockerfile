FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy shared package
COPY shared-package /app/shared-package

# Install shared package
RUN pip install --no-cache-dir /app/shared-package

# Copy data collector
COPY microservices/data-collector /app

# Install requirements
RUN pip install --no-cache-dir \
    redis \
    geopy \
    sqlalchemy \
    psycopg2-binary \
    httpx

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV REDIS_URL=redis://redis:6379/0

# Run the data collector
CMD ["python", "main.py"]

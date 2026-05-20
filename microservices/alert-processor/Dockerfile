FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install requirements (before copying code for better layer caching)
COPY microservices/alert-processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared package and install
COPY shared-package /app/shared-package
RUN pip install --no-cache-dir /app/shared-package

# Copy alert processor code
COPY microservices/alert-processor /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV REDIS_URL=redis://redis:6379/0

# Expose debug port
EXPOSE 5679

# Run the alert consumer with debugpy (removed --wait-for-client to allow normal startup)
CMD ["python", "-Xfrozen_modules=off", "-m", "debugpy", "--listen", "0.0.0.0:5679", "main.py"]

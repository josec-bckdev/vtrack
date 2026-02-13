FROM python:3.11-slim

WORKDIR /app

# Copy shared package first (from build context root)
COPY shared-package /tmp/shared-package
RUN pip install --no-cache-dir /tmp/shared-package && \
    rm -rf /tmp/shared-package

# Copy notification service code
COPY microservices/notification-sender /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
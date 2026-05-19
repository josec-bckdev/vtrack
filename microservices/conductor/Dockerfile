FROM python:3.12-slim

WORKDIR /app

COPY microservices/conductor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY microservices/conductor/ ./conductor/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "conductor.main"]

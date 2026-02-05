# Use the official Python image as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy Alembic config and migration scripts so alembic is available in-container
COPY alembic.ini /app/
COPY alembic /app/alembic

# Copy the application code into the container
COPY app/ /app/app/

# Command to run the application (using Uvicorn)
# We will use the command in docker-compose for easier configuration
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

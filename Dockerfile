# Use official Python image as base
FROM python:3.12.3-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements if present
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (adjust if needed for FastAPI/Uvicorn)
EXPOSE 8001

# Default command to run the API (adjust if needed)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

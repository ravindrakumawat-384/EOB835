FROM python:3.11-slim
 
WORKDIR /app
 
# ---- System runtime dependencies ----
RUN apt-get update && apt-get install -y \
    libpq5 \
    libmagic1 \
    tesseract-ocr \
    poppler-utils \
    libjpeg62-turbo \
    zlib1g \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*
 
# ---- Python dependencies ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# ---- App code ----
COPY . .
 
EXPOSE 8001
 
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

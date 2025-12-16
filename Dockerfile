FROM python:3.10-slim-bookworm

# 1. Install System Dependencies (Tesseract, Poppler, OpenCV libs)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    libmagic-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Set working directory
WORKDIR /app

# 3. Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Create necessary directories for persistence
RUN mkdir -p /app/data/uploads /app/data/processed /app/models

# 5. Set Environment Variables
# Tell Unstructured to cache models in our mounted volume
ENV TORCH_HOME=/app/models
ENV HF_HOME=/app/models
ENV UNSTRUCTURED_HI_RES_MODEL_NAME=yolox

# 6. Copy the rest of the application
COPY . .

# 7. Expose port
EXPOSE 5000

# 8. Command to run
CMD ["python", "app.py"]
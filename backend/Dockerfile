FROM python:3.11-slim

# Install dependencies including stress tool
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libffi-dev \
    stress \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

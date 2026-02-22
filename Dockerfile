FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements
COPY requirements.txt .

# Installa PyTorch CPU-only PRIMA (evita download ~3GB di CUDA libs)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# Copia codice
COPY . .

# Crea directory logs
RUN mkdir -p /app/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "bot/main.py"]

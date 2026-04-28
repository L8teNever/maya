FROM python:3.11-slim

WORKDIR /app

# Die OpenCV/MediaPipe Bibliotheken benötigen einige System-Pakete
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App Code kopieren
COPY . .

# Verzeichnisse sicherstellen
RUN mkdir -p images/raw images/aligned static

EXPOSE 8000

# Server starten
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

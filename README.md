# MAYA - Daily Selfie Timelapse 📸✨

MAYA ist eine moderne Progressive Web App (PWA) im schicken **Android 15 Material Design** (Material You). Sie erinnert dich täglich daran, ein Foto von dir zu schießen, und kreiert über Zeit eine nahtlose Timeline!

Dank der eingebauten **KI (MediaPipe)** erkennt MAYA automatisch dein Gesicht auf dem Foto. Es sucht deine Pupillen, richtet das Bild kerzengerade aus und skaliert es so, dass deine Augen auf *jedem* Foto exakt auf derselben Position bleiben. So entsteht später der perfekte **Timelase-Effekt** ohne Ruckeln!

## Features 🚀
- 🧠 **Smart Face Alignment:** Erkennt Augen via MediaPipe und richtet Bilder Millimeter-genau aus.
- 🎨 **Android 15 Design:** Ein frisches, sauberes Material 3 Design mit dynamischen UI-Elementen.
- 📱 **Progressive Web App (PWA):** Lade die App direkt auf deinen Smartphone-Homescreen.
- ⏰ **Tägliche Push-Erinnerung:** Lokales Push-System über den Service Worker via Notification Triggers API.
- 🐳 **Docker Bereitstellung:** Komplette Pipeline mit automatischer Veröffentlichung via GitHub Actions (`ghcr.io`).

---

## Installation & Ausführen 🐳

Die App wird als voll funktionsfähiger Docker Container auf der GitHub Container Registry (ghcr.io) bereitgestellt.

### Methode 1: Docker Compose (Empfohlen)

Es wird empfohlen, `docker-compose` zu nutzen, um die geschossenen Bilder in deinem lokalen Dateisystem zu sichern.

1. Erstelle eine `docker-compose.yml` (oder lade sie von diesem Repo herunter):
```yaml
version: '3.8'
services:
  maya-app:
    image: ghcr.io/l8tenever/maya:master
    container_name: maya-app
    ports:
      - "8000:8000"
    volumes:
      - ./maya_data/raw:/app/images/raw
      - ./maya_data/aligned:/app/images/aligned
    restart: unless-stopped
```
2. Starte die App:
```bash
docker-compose up -d
```
3. Öffne `http://localhost:8000` in deinem Browser!

### Methode 2: Simpler Docker Run

Schnell starten ohne Ordner-Synchronisierung:
```bash
docker run -d -p 8000:8000 --name maya-app ghcr.io/l8tenever/maya:master
```

---

## Lokale Entwicklung (Python) 🐍

Wenn du den Code verändern oder ohne Docker laufen lassen willst:

1. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
2. Server starten:
   ```bash
   python main.py
   ```
   *(Erfordert: `libgl1-mesa-glx` und `libglib2.0-0` auf Linux-basierten Systemen für OpenCV)*

---

*Made with ❤️ by AI*

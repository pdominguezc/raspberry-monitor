# Raspberry Pi Monitor

Monitoreo de CPU, memoria, disco, red, temperatura, uptime y accesos al sitio
de una Raspberry Pi, accesible desde:

- **El sitio web** alojado en la propia Raspberry Pi (dashboard en tiempo real).
- **Una PWA instalable en Android** (el mismo sitio, con "Agregar a pantalla de inicio").
- **Home Assistant** (sensores REST, sin necesidad de broker MQTT).
- **Cualquier programa/script** que consuma la API REST/WebSocket.

Todo accesible desde fuera de la red local vía **Cloudflare Tunnel**, sin abrir
puertos en el router.

## Arquitectura

```
┌─────────────┐   HTTPS (Cloudflare Tunnel)   ┌───────────────────────────┐
│  Internet   │ ─────────────────────────────▶│      Raspberry Pi          │
│ (HA, PWA,   │                                │  ┌─────────────────────┐  │
│  navegador) │                                │  │ cloudflared (túnel) │  │
└─────────────┘                                │  └──────────┬──────────┘  │
                                                │             │ localhost:8000
                                                │  ┌──────────▼──────────┐  │
                                                │  │ FastAPI (uvicorn)   │  │
                                                │  │  - REST /api/*      │  │
                                                │  │  - WebSocket /ws/*  │  │
                                                │  │  - sirve frontend/  │  │
                                                │  │  - psutil (métricas)│  │
                                                │  │  - SQLite (histórico│  │
                                                │  │    y accesos)       │  │
                                                │  └──────────────────────┘  │
                                                └───────────────────────────┘
```

## Estructura del proyecto

```
backend/            API FastAPI + recolección de métricas (psutil) + SQLite
frontend/           Dashboard web / PWA (HTML, CSS, JS vanilla, Chart.js)
homeassistant/      Config de ejemplo para integrar sensores en HA
cloudflared/        Config de ejemplo y guía del túnel de Cloudflare
systemd/            Servicio para que el backend arranque solo con la Pi
```

## 1. Instalación en la Raspberry Pi

```bash
git clone <este-repo> raspberry-monitor   # o copia la carpeta por scp
cd raspberry-monitor/backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env y define un API_TOKEN fuerte:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
nano .env
```

Prueba en local:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abre `http://<ip-de-la-pi>:8000` en el navegador: te pedirá el token (el mismo
`API_TOKEN` del `.env`) y luego verás el dashboard en vivo.

## 2. Dejarlo corriendo siempre (systemd)

```bash
sudo cp ../systemd/raspberry-monitor.service /etc/systemd/system/
sudo nano /etc/systemd/system/raspberry-monitor.service   # ajusta usuario/rutas si es necesario
sudo systemctl daemon-reload
sudo systemctl enable --now raspberry-monitor
sudo systemctl status raspberry-monitor
```

## 3. Exponer con Cloudflare Tunnel

Sigue la guía en [`cloudflared/README.md`](./cloudflared/README.md). Al final
tendrás `https://rpi.tu-dominio.com` apuntando al dashboard, sin abrir puertos.

## 4. Instalar como app en Android (PWA)

1. Abre `https://rpi.tu-dominio.com` en Chrome en tu celular.
2. Ingresa el token cuando lo pida (queda guardado localmente en el navegador).
3. Menú (⋮) → **"Agregar a pantalla de inicio" / "Instalar app"**.
4. Queda con ícono propio y abre en modo standalone (sin barra del navegador).

## 5. Integrar con Home Assistant

Copia el contenido de [`homeassistant/configuration_snippet.yaml`](./homeassistant/configuration_snippet.yaml)
a tu `configuration.yaml` (o inclúyelo con `!include`), agrega el token a
`secrets.yaml` como `raspberry_monitor_token`, ajusta el hostname y reinicia
Home Assistant. Se eligió **REST polling en vez de MQTT** para no tener que
instalar un broker adicional en la Pi (menos consumo de RAM/CPU); si más
adelante quieres autodiscovery vía MQTT (por ejemplo porque ya tienes un
broker corriendo para otros dispositivos), se puede agregar sin tocar el
backend.

## API

Todas las rutas (excepto `/api/health`) requieren el header
`Authorization: Bearer <API_TOKEN>` (o `?token=` para el WebSocket).

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Chequeo de salud, sin auth |
| GET | `/api/metrics` | Foto instantánea de CPU/memoria/disco/red/temperatura/uptime |
| GET | `/api/metrics/history?minutes=60` | Histórico de métricas (SQLite) |
| GET | `/api/access/stats` | Estadísticas de accesos al sitio (hoy, 7 días, IPs únicas, recientes) |
| WS | `/ws/metrics?token=...` | Push de una nueva foto cada `SAMPLE_INTERVAL_SECONDS` |

## Notas

- Las métricas de disco se leen por cada punto de montaje real (no solo `/`).
- La temperatura se lee de `/sys/class/thermal/thermal_zone0/temp` (funciona
  en cualquier Raspberry Pi OS sin dependencias extra).
- El histórico y el log de accesos se podan automáticamente según
  `HISTORY_RETENTION_DAYS` / `ACCESS_LOG_RETENTION_DAYS` en `.env`.
- El "conteo de accesos" registra cada request HTTP al sitio/API (método,
  ruta, IP, user-agent, código de estado); si además quieres accesos SSH o
  intentos de login fallidos, se puede sumar leyendo `/var/log/auth.log` en
  una futura iteración.

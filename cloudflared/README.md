# Exponer Raspberry Pi Monitor con Cloudflare Tunnel

Esta guía asume que `cloudflared` corre **en la misma Raspberry Pi** que el backend
(`app.main:app` escuchando en `localhost:8000`), y que tu dominio ya está en Cloudflare.

## 1. Instalar cloudflared en la Pi

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
cloudflared --version
```
(Usa `cloudflared-linux-arm.deb` si tu Pi es de 32 bits.)

## 2. Autenticarse y crear el túnel

```bash
cloudflared tunnel login
cloudflared tunnel create raspberry-monitor
```

Esto crea un archivo de credenciales en `~/.cloudflared/<TUNNEL_ID>.json` y te
da el `<TUNNEL_ID>` que necesitas para el siguiente paso.

## 3. Configurar el túnel

Copia [`config.yml.example`](./config.yml.example) a `~/.cloudflared/config.yml`,
reemplaza `<TUNNEL_ID>` y el hostname por los tuyos.

## 4. Enrutar el DNS

```bash
cloudflared tunnel route dns raspberry-monitor rpi.tu-dominio.com
```

## 5. Probar y dejarlo como servicio

```bash
cloudflared tunnel run raspberry-monitor   # prueba manual
sudo cloudflared service install           # instala como servicio systemd
sudo systemctl enable --now cloudflared
```

## 6. Protege el acceso (recomendado, además del token de la API)

La API ya exige un `API_TOKEN` propio (ver `backend/.env`), pero como quedará
expuesta a Internet conviene sumar una capa más con **Cloudflare Access**:

1. En Cloudflare Zero Trust → Access → Applications, crea una aplicación
   "Self-hosted" apuntando a `rpi.tu-dominio.com`.
2. Define una política que solo permita tu email (o los emails de tu familia).
3. Así, antes de llegar siquiera al login de la app, Cloudflare pedirá
   autenticación (código por email, Google, etc).

Para la app Android (PWA) y Home Assistant esto normalmente no es un problema:
Cloudflare Access soporta "Service Tokens" para clientes que no pueden hacer
login interactivo — puedes generar uno y agregarlo como header adicional
(`CF-Access-Client-Id` / `CF-Access-Client-Secret`) en la configuración del
sensor REST de Home Assistant si decides activar Access.

## Notas de seguridad

- Nunca expongas el puerto 8000 directamente en tu router; todo el tráfico
  debe pasar por el túnel de Cloudflare (que no requiere abrir puertos).
- Usa siempre HTTPS (Cloudflare lo maneja automáticamente en el hostname
  público).
- Rota el `API_TOKEN` si sospechas que se filtró, y actualízalo en Home
  Assistant, la PWA (borra `localStorage`) y cualquier otro cliente.

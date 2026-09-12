from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from . import config, database, metrics
from .auth import verify_token

logger = logging.getLogger("raspberry_monitor")
logging.basicConfig(level=logging.INFO)

_ws_clients: set[WebSocket] = set()


async def _sampler_loop() -> None:
    while True:
        try:
            snapshot = metrics.collect_snapshot()
            database.insert_sample(snapshot)
            dead = set()
            for ws in _ws_clients:
                try:
                    await ws.send_json(snapshot)
                except Exception:
                    dead.add(ws)
            _ws_clients.difference_update(dead)
        except Exception:
            logger.exception("Error muestreando métricas")
        await asyncio.sleep(config.SAMPLE_INTERVAL_SECONDS)


async def _prune_loop() -> None:
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            database.prune_old_samples()
        except Exception:
            logger.exception("Error limpiando datos antiguos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    sampler_task = asyncio.create_task(_sampler_loop())
    prune_task = asyncio.create_task(_prune_loop())
    yield
    sampler_task.cancel()
    prune_task.cancel()


app = FastAPI(title="Raspberry Pi Monitor", lifespan=lifespan)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Registra cada request HTTP para poder mostrar estadísticas de acceso."""

    EXCLUDED_PREFIXES = ("/static", "/favicon", "/manifest.json", "/service-worker.js", "/api/access/stats")

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        try:
            if not request.url.path.startswith(self.EXCLUDED_PREFIXES):
                client_ip = request.headers.get("cf-connecting-ip") or (
                    request.client.host if request.client else "unknown"
                )
                database.insert_access(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    client_ip=client_ip,
                    user_agent=request.headers.get("user-agent", ""),
                )
        except Exception:
            logger.exception("Error registrando acceso")
        return response


class NoEdgeCacheMiddleware(BaseHTTPMiddleware):
    """Evita que Cloudflare (u otros proxies/navegadores) cacheen agresivamente
    el frontend estático, para que los despliegues se reflejen de inmediato
    sin depender de purgar el caché manualmente."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith(("/api/", "/ws/")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


app.add_middleware(NoEdgeCacheMiddleware)
app.add_middleware(AccessLogMiddleware)


@app.get("/api/health")
async def health():
    """Endpoint público sin autenticación, útil para Cloudflare/uptime checks."""
    return {"status": "ok"}


@app.get("/api/metrics", dependencies=[Depends(verify_token)])
async def get_metrics():
    return metrics.collect_snapshot()


@app.get("/api/metrics/history", dependencies=[Depends(verify_token)])
async def get_history(minutes: int = 60):
    minutes = max(1, min(minutes, 60 * 24 * config.HISTORY_RETENTION_DAYS))
    return {"minutes": minutes, "samples": database.query_history(minutes)}


@app.get("/api/access/stats", dependencies=[Depends(verify_token)])
async def get_access_stats():
    return database.access_stats()


@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if token != config.API_TOKEN:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        await websocket.send_json(metrics.collect_snapshot())
        while True:
            # Mantiene la conexión viva; no esperamos mensajes del cliente.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado")
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


# Sirve el frontend estático (debe montarse al final para no tapar las rutas /api).
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")

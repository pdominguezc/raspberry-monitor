import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

API_TOKEN = os.getenv("API_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "monitor.db"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SAMPLE_INTERVAL_SECONDS = int(os.getenv("SAMPLE_INTERVAL_SECONDS", "30"))
HISTORY_RETENTION_DAYS = int(os.getenv("HISTORY_RETENTION_DAYS", "14"))
ACCESS_LOG_RETENTION_DAYS = int(os.getenv("ACCESS_LOG_RETENTION_DAYS", "30"))
FRONTEND_DIR = os.getenv("FRONTEND_DIR", str(BASE_DIR.parent / "frontend"))

if not API_TOKEN:
    raise RuntimeError(
        "API_TOKEN no está configurado. Copia backend/.env.example a backend/.env "
        "y define un token seguro antes de iniciar el servidor."
    )

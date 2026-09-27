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


def _optional_float(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").strip()
ALERT_CPU_PERCENT = _optional_float("ALERT_CPU_PERCENT")
ALERT_MEMORY_PERCENT = _optional_float("ALERT_MEMORY_PERCENT")
ALERT_DISK_PERCENT = _optional_float("ALERT_DISK_PERCENT")
ALERT_TEMPERATURE_C = _optional_float("ALERT_TEMPERATURE_C")
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "30"))

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes", "on")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER

if not API_TOKEN:
    raise RuntimeError(
        "API_TOKEN no está configurado. Copia backend/.env.example a backend/.env "
        "y define un token seguro antes de iniciar el servidor."
    )

"""Alertas por correo cuando alguna métrica supera su umbral configurado.

Se revisa en cada muestreo (ver main.py:_sampler_loop). Por cada métrica se
guarda en memoria cuándo fue la última vez que se avisó, para no mandar un
correo nuevo cada 30 segundos mientras la métrica siga alta — solo re-avisa
después de ALERT_COOLDOWN_MINUTES. Cuando la métrica vuelve a estar bajo el
umbral después de haber avisado, manda un correo de "se normalizó".

Nunca lanza excepción hacia afuera: un error de SMTP no debe cortar el
muestreo de métricas.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from . import config

logger = logging.getLogger("raspberry_monitor")

# key -> último momento en que se avisó de esa métrica en particular
_last_alert_at: dict[str, datetime] = {}
# keys actualmente por sobre su umbral (para saber cuándo mandar "se normalizó")
_active_alerts: set[str] = set()


def _send_email(subject: str, body: str) -> None:
    if not config.ALERT_EMAIL_TO or not config.SMTP_HOST or not config.SMTP_USER:
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = config.ALERT_EMAIL_TO
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            if config.SMTP_USE_TLS:
                server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        logger.exception("No se pudo enviar el correo de alerta")


def _check_one(key: str, label: str, value: float | None, threshold: float | None, unit: str = "%") -> None:
    if value is None or threshold is None:
        return

    now = datetime.now(timezone.utc)
    over_threshold = value >= threshold

    if over_threshold:
        last = _last_alert_at.get(key)
        due = last is None or (now - last) >= timedelta(minutes=config.ALERT_COOLDOWN_MINUTES)
        if due:
            _send_email(
                f"⚠️ Raspberry Pi: {label} alto ({value:.1f}{unit})",
                f"{label} está en {value:.1f}{unit}, por sobre el umbral configurado de {threshold:.1f}{unit}.\n\n"
                f"Revisa el dashboard en https://rpi.pablodominguez.cl/",
            )
            _last_alert_at[key] = now
            _active_alerts.add(key)
    elif key in _active_alerts:
        _send_email(
            f"✅ Raspberry Pi: {label} volvió a la normalidad ({value:.1f}{unit})",
            f"{label} bajó a {value:.1f}{unit}, ya por debajo del umbral de {threshold:.1f}{unit}.",
        )
        _active_alerts.discard(key)
        _last_alert_at.pop(key, None)


def check_thresholds(snapshot: dict) -> None:
    """Revisa el snapshot recién muestreado contra los umbrales configurados
    (ver .env: ALERT_CPU_PERCENT, ALERT_MEMORY_PERCENT, ALERT_DISK_PERCENT,
    ALERT_TEMPERATURE_C) y manda un correo si corresponde. Sin umbral
    configurado para una métrica, esa métrica simplemente no se revisa."""
    try:
        _check_one("cpu", "Uso de CPU", snapshot["cpu"]["percent"], config.ALERT_CPU_PERCENT)
        _check_one("memory", "Uso de memoria", snapshot["memory"]["percent"], config.ALERT_MEMORY_PERCENT)
        _check_one("temperature", "Temperatura", snapshot["temperature_c"], config.ALERT_TEMPERATURE_C, unit="°C")
        for disk in snapshot["disks"]:
            _check_one(
                f"disk:{disk['mountpoint']}",
                f"Uso de disco ({disk['mountpoint']})",
                disk["percent"],
                config.ALERT_DISK_PERCENT,
            )
    except Exception:
        logger.exception("Error revisando umbrales de alerta")

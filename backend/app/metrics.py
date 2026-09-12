"""Recolección de métricas del sistema (CPU, memoria, disco, red, temperatura, uptime)."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import psutil

# psutil.cpu_percent necesita una primera llamada "de calentamiento" para que
# las siguientes lecturas no bloqueantes sean precisas.
psutil.cpu_percent(percpu=True)

_last_net: dict | None = None
_last_net_time: float | None = None


def _read_cpu_temperature_c() -> float | None:
    """Lee la temperatura del SoC desde el sysfs del kernel (funciona en toda Raspberry Pi OS)."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            raw = f.read().strip()
        return round(int(raw) / 1000.0, 1)
    except (FileNotFoundError, ValueError, PermissionError):
        return None


def _disks() -> list[dict]:
    result = []
    seen_mounts = set()
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint in seen_mounts:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        seen_mounts.add(part.mountpoint)
        result.append(
            {
                "mountpoint": part.mountpoint,
                "device": part.device,
                "fstype": part.fstype,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "percent": usage.percent,
            }
        )
    return result


def _network() -> dict:
    global _last_net, _last_net_time

    now = time.monotonic()
    counters = psutil.net_io_counters(pernic=True)

    interfaces = {}
    rates = {}
    if _last_net is not None and _last_net_time is not None:
        elapsed = max(now - _last_net_time, 1e-6)
        for name, c in counters.items():
            prev = _last_net.get(name)
            if prev is not None:
                rates[name] = {
                    "sent_bytes_per_sec": max((c.bytes_sent - prev.bytes_sent) / elapsed, 0),
                    "recv_bytes_per_sec": max((c.bytes_recv - prev.bytes_recv) / elapsed, 0),
                }

    for name, c in counters.items():
        if name == "lo":
            continue
        interfaces[name] = {
            "bytes_sent": c.bytes_sent,
            "bytes_recv": c.bytes_recv,
            "packets_sent": c.packets_sent,
            "packets_recv": c.packets_recv,
            "errin": c.errin,
            "errout": c.errout,
            "rate": rates.get(name),
        }

    _last_net = counters
    _last_net_time = now
    return interfaces


def collect_snapshot() -> dict:
    """Devuelve una foto instantánea de todas las métricas del sistema."""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    load1, load5, load15 = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (None, None, None)
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu": {
            "percent": psutil.cpu_percent(percpu=False),
            "percent_per_core": psutil.cpu_percent(percpu=True),
            "core_count": psutil.cpu_count(logical=True),
            "load_avg_1m": load1,
            "load_avg_5m": load5,
            "load_avg_15m": load15,
        },
        "memory": {
            "total_bytes": vm.total,
            "used_bytes": vm.used,
            "available_bytes": vm.available,
            "percent": vm.percent,
        },
        "swap": {
            "total_bytes": swap.total,
            "used_bytes": swap.used,
            "percent": swap.percent,
        },
        "disks": _disks(),
        "network": _network(),
        "temperature_c": _read_cpu_temperature_c(),
        "uptime_seconds": uptime_seconds,
        "boot_time": datetime.fromtimestamp(boot_time, tz=timezone.utc).isoformat(),
    }

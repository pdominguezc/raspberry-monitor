"""Persistencia en SQLite: histórico de métricas y registro de accesos."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

_local = threading.local()


def _connect() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db() -> None:
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metric_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            cpu_percent REAL,
            memory_percent REAL,
            swap_percent REAL,
            disk_root_percent REAL,
            temperature_c REAL,
            payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metric_samples_ts ON metric_samples (ts);

        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status_code INTEGER,
            client_ip TEXT,
            user_agent TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_access_log_ts ON access_log (ts);
        """
    )
    conn.commit()


def insert_sample(snapshot: dict) -> None:
    conn = _connect()
    disk_root = next((d["percent"] for d in snapshot["disks"] if d["mountpoint"] == "/"), None)
    conn.execute(
        """INSERT INTO metric_samples
           (ts, cpu_percent, memory_percent, swap_percent, disk_root_percent, temperature_c, payload)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            snapshot["timestamp"],
            snapshot["cpu"]["percent"],
            snapshot["memory"]["percent"],
            snapshot["swap"]["percent"],
            disk_root,
            snapshot["temperature_c"],
            json.dumps(snapshot),
        ),
    )
    conn.commit()


def query_history(minutes: int) -> list[dict]:
    conn = _connect()
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    rows = conn.execute(
        """SELECT ts, cpu_percent, memory_percent, swap_percent, disk_root_percent, temperature_c
           FROM metric_samples WHERE ts >= ? ORDER BY ts ASC""",
        (since,),
    ).fetchall()
    return [dict(r) for r in rows]


def prune_old_samples() -> None:
    conn = _connect()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=config.HISTORY_RETENTION_DAYS)).isoformat()
    conn.execute("DELETE FROM metric_samples WHERE ts < ?", (cutoff,))
    access_cutoff = (datetime.now(timezone.utc) - timedelta(days=config.ACCESS_LOG_RETENTION_DAYS)).isoformat()
    conn.execute("DELETE FROM access_log WHERE ts < ?", (access_cutoff,))
    conn.commit()


def insert_access(method: str, path: str, status_code: int, client_ip: str, user_agent: str) -> None:
    conn = _connect()
    conn.execute(
        """INSERT INTO access_log (ts, method, path, status_code, client_ip, user_agent)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (datetime.now(timezone.utc).isoformat(), method, path, status_code, client_ip, user_agent),
    )
    conn.commit()


def access_stats() -> dict:
    conn = _connect()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()

    total = conn.execute("SELECT COUNT(*) AS c FROM access_log").fetchone()["c"]
    today = conn.execute("SELECT COUNT(*) AS c FROM access_log WHERE ts >= ?", (today_start,)).fetchone()["c"]
    last_7_days = conn.execute("SELECT COUNT(*) AS c FROM access_log WHERE ts >= ?", (week_start,)).fetchone()["c"]

    top_paths = conn.execute(
        """SELECT path, COUNT(*) AS hits FROM access_log
           WHERE ts >= ? GROUP BY path ORDER BY hits DESC LIMIT 10""",
        (week_start,),
    ).fetchall()

    recent = conn.execute(
        """SELECT ts, method, path, status_code, client_ip FROM access_log
           ORDER BY ts DESC LIMIT 20"""
    ).fetchall()

    unique_ips_week = conn.execute(
        "SELECT COUNT(DISTINCT client_ip) AS c FROM access_log WHERE ts >= ?", (week_start,)
    ).fetchone()["c"]

    two_weeks_start = (now - timedelta(days=14)).isoformat()
    daily_rows = conn.execute(
        """SELECT substr(ts, 1, 10) AS day, COUNT(*) AS hits FROM access_log
           WHERE ts >= ? GROUP BY day ORDER BY day ASC""",
        (two_weeks_start,),
    ).fetchall()
    daily_by_date = {r["day"]: r["hits"] for r in daily_rows}
    daily_counts = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_counts.append({"date": day, "hits": daily_by_date.get(day, 0)})

    return {
        "total": total,
        "today": today,
        "last_7_days": last_7_days,
        "unique_ips_last_7_days": unique_ips_week,
        "top_paths_last_7_days": [dict(r) for r in top_paths],
        "recent": [dict(r) for r in recent],
        "daily_counts_last_14_days": daily_counts,
    }

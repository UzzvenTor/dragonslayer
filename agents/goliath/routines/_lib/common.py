"""Голиаф v2 — общие helpers для скиллов и routines.

Дизайн: каждый скилл может быть запущен автономно (`python skill.py`).
Этот модуль — необязательная общая инфра: env loader + Postgres connection +
date math для 3 окон. Скиллы либо импортируют (если в sys.path), либо дублируют.

Использование:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "routines"))
    from _lib.common import load_env, pg_conn, windows_for, force_ipv4
"""
from __future__ import annotations

import datetime
import os
import socket
import sys
from pathlib import Path

# ─── IPv4 force (для api.direct.yandex.com на Windows) ───

def force_ipv4():
    """Idempotent monkey-patch socket.getaddrinfo на IPv4-only.
    Безвредно на Linux. Без него Я.Директ API на Windows глохнет."""
    if not hasattr(socket, "AF_INET"):
        return
    if getattr(force_ipv4, "_applied", False):
        return
    _orig = socket.getaddrinfo
    def _ipv4_only(host, *a, **kw):
        return [r for r in _orig(host, *a, **kw) if r[0] == socket.AF_INET] or _orig(host, *a, **kw)
    socket.getaddrinfo = _ipv4_only
    force_ipv4._applied = True


# ─── env loader ───

_ENV_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / ".env",     # agents/goliath/.env (cloud + local)
]
# В local-режиме (Windows) можно подмешать legacy .env как fallback. В cloud
# routine — переменные окружения уже инжектируются через routine config.
_LEGACY_LOCAL_ENV = Path(r"I:\neuro\GENERAL CLAUDE CODE\Zerocoder\dragonslayer\goliath_daily\.env")
if _LEGACY_LOCAL_ENV.exists():
    _ENV_CANDIDATES.append(_LEGACY_LOCAL_ENV)


def load_env(extra_paths: list[Path] | None = None) -> Path | None:
    """Загружает первый существующий .env. Возвращает путь использованного .env."""
    paths = list(extra_paths or []) + _ENV_CANDIDATES
    try:
        from dotenv import load_dotenv
        for p in paths:
            if p.exists():
                load_dotenv(p)
                return p
    except ImportError:
        for p in paths:
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
            return p
    return None


# ─── Postgres connection (goliath schema) ───

def pg_conn(autocommit: bool = False):
    """psycopg2-connection в БД kurzemnek с search_path TO goliath, public.
    Поднимает OSError если PG_PASSWORD пуст."""
    import psycopg2
    pwd = os.environ.get("PG_PASSWORD", "")
    if not pwd:
        raise OSError("PG_PASSWORD пуст — невозможно подключиться к goliath PG")
    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "rc1b-nftoajilh0nnj0gf.mdb.yandexcloud.net"),
        port=int(os.environ.get("PG_PORT", 6432)),
        user=os.environ.get("PG_USER", "kurzemnek_app"),
        password=pwd,
        dbname=os.environ.get("PG_DB", "kurzemnek"),
        sslmode="require",
        connect_timeout=15,
    )
    if autocommit:
        conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET search_path TO goliath, public")
    return conn


# ─── Окна (вчера / неделя / MTD) ───

def windows_for(yday: datetime.date) -> dict[str, tuple[datetime.date, datetime.date]]:
    """Возвращает 3 окна для отчёта.

    yday  — конкретная дата (одна и та же дата от-до)
    week  — Пн → yday (неделя yday)
    mtd   — 1-е число → yday
    """
    week_start = yday - datetime.timedelta(days=yday.weekday())
    mtd_start = yday.replace(day=1)
    return {
        "yday": (yday, yday),
        "week": (week_start, yday),
        "mtd":  (mtd_start, yday),
    }

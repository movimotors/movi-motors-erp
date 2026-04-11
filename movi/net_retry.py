"""Reintentos ante fallos HTTP transitorios (p. ej. Streamlit Cloud ↔ Supabase)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import httpx

T = TypeVar("T")

_TRANSIENT = (
    httpx.ReadError,
    httpx.ConnectError,
    httpx.WriteError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)


def run_transient_http_retry(fn: Callable[[], T], *, attempts: int = 4, base_delay: float = 0.35) -> T:
    """Ejecuta ``fn``; ante cortes típicos de lectura/conexión reintenta con backoff exponencial."""
    last: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except _TRANSIENT as e:
            last = e
            if i >= attempts - 1:
                raise
            time.sleep(base_delay * (2**i))
    raise AssertionError("unreachable") from last

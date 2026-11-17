# backend/app/core/rate_limit.py
"""Dependency-free, in-memory sliding-window rate limiter (per client IP, per process).

Limits are per worker process. For multi-instance deployments, also rate limit at the
reverse proxy (nginx `limit_req`) or move the counters to Redis.
"""
import asyncio
import time
from collections import deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings

_WINDOW_SECONDS = 60.0
_MAX_TRACKED_KEYS = 50_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: Dict[Tuple[str, str], Deque[float]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _bucket(path: str) -> Tuple[str, int]:
        if path.startswith("/auth/token"):
            return "login", settings.rate_limit_login_per_minute
        if path.startswith("/ml"):
            return "ml", settings.rate_limit_ml_per_minute
        return "default", settings.rate_limit_default_per_minute

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled or request.method == "OPTIONS" or request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket, limit = self._bucket(request.url.path)
        key = (client_ip, bucket)
        now = time.monotonic()

        async with self._lock:
            if len(self._hits) > _MAX_TRACKED_KEYS:
                # Drop idle entries so memory can't be exhausted by many source IPs
                cutoff = now - _WINDOW_SECONDS
                for k in [k for k, q in self._hits.items() if not q or q[-1] < cutoff]:
                    del self._hits[k]
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - _WINDOW_SECONDS:
                q.popleft()
            if len(q) >= limit:
                retry_after = int(_WINDOW_SECONDS - (now - q[0])) + 1
                return JSONResponse(
                    {"detail": "Too many requests"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

        return await call_next(request)

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Small fail-open Redis JSON cache with deterministic cache keys."""

    @staticmethod
    def fingerprint(namespace: str, value: Any) -> str:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{settings.redis_key_prefix}:{namespace}:{digest}"

    @staticmethod
    def key(namespace: str, identifier: str) -> str:
        safe_identifier = "".join(
            character for character in identifier if character.isalnum() or character in "-_"
        )
        return f"{settings.redis_key_prefix}:{namespace}:{safe_identifier}"

    async def _client(self):
        from redis.asyncio import Redis

        return Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_connect_timeout_seconds,
        )

    async def get_json(self, key: str) -> dict[str, Any] | None:
        if not settings.redis_cache_enabled:
            return None
        client = await self._client()
        try:
            value = await client.get(key)
            if not value:
                return None
            result = json.loads(value)
            logger.info("Redis cache hit key=%s", key)
            return result if isinstance(result, dict) else None
        except Exception as exc:
            logger.warning("Redis cache read skipped key=%s reason=%s", key, type(exc).__name__)
            return None
        finally:
            await client.aclose()

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if not settings.redis_cache_enabled:
            return
        client = await self._client()
        try:
            await client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
            logger.info("Redis cache stored key=%s ttl_seconds=%s", key, ttl_seconds)
        except Exception as exc:
            logger.warning("Redis cache write skipped key=%s reason=%s", key, type(exc).__name__)
        finally:
            await client.aclose()

    async def health(self) -> bool:
        if not settings.redis_cache_enabled:
            return False
        client = await self._client()
        try:
            return bool(await client.ping())
        except Exception:
            return False
        finally:
            await client.aclose()


cache = RedisCache()

"""
Redis-compatible in-memory cache.

Provides a full-featured cache that mirrors Redis semantics including:
- String operations (get, set, delete, exists, incr)
- Set operations (sadd, sismember, srem)
- Sorted-set operations (zadd, zrangebyscore, zremrangebyscore, zcard)
- Hash operations (hset, hget, hgetall)
- TTL / expiry with lazy eviction + background sweep
- Pipeline batching
"""

from __future__ import annotations

import asyncio
import time
from typing import Any


class InMemoryCache:
    """Drop-in async cache that behaves like Redis for development."""

    def __init__(self, cleanup_interval: float = 60.0) -> None:
        """Initialise the cache.

        Args:
            cleanup_interval: Seconds between background TTL sweeps.
        """
        # Main key→value store (strings, sets, sorted sets, hashes)
        self._store: dict[str, Any] = {}
        # key → absolute expiry timestamp (epoch seconds)
        self._expiries: dict[str, float] = {}
        # Tracks type per key: "string" | "set" | "zset" | "hash"
        self._types: dict[str, str] = {}

        self._cleanup_interval = cleanup_interval
        self._cleanup_task: asyncio.Task[None] | None = None
        self._closed = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background TTL cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the background cleanup and clear all data."""
        self._closed = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def clear(self) -> None:
        """Flush all keys."""
        self._store.clear()
        self._expiries.clear()
        self._types.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_expired(self, key: str) -> bool:
        """Check whether *key* has expired (lazy eviction)."""
        exp = self._expiries.get(key)
        if exp is not None and time.time() > exp:
            self._evict(key)
            return True
        return False

    def _evict(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiries.pop(key, None)
        self._types.pop(key, None)

    async def _cleanup_loop(self) -> None:
        """Periodically sweep expired keys."""
        while not self._closed:
            try:
                await asyncio.sleep(self._cleanup_interval)
                now = time.time()
                expired_keys = [
                    k for k, exp in list(self._expiries.items()) if now > exp
                ]
                for k in expired_keys:
                    self._evict(k)
            except asyncio.CancelledError:
                break

    def _assert_type(self, key: str, expected: str) -> None:
        """Raise if the key exists with a different type."""
        existing = self._types.get(key)
        if existing is not None and existing != expected:
            raise TypeError(
                f"WRONGTYPE Operation against key '{key}' "
                f"holding the wrong kind of value "
                f"(expected {expected}, got {existing})"
            )

    # ------------------------------------------------------------------
    # String commands
    # ------------------------------------------------------------------

    async def get(self, key: str) -> str | None:
        """Get the string value of a key, or ``None`` if missing/expired."""
        if self._is_expired(key):
            return None
        self._assert_type(key, "string")
        return self._store.get(key)

    async def set(
        self, key: str, value: str, ttl: int | None = None
    ) -> None:
        """Set a string value with optional TTL in seconds."""
        self._store[key] = value
        self._types[key] = "string"
        if ttl is not None and ttl > 0:
            self._expiries[key] = time.time() + ttl
        elif key in self._expiries:
            # No TTL specified → remove any existing expiry
            del self._expiries[key]

    async def exists(self, key: str) -> bool:
        """Check if key exists (lazy expiry honoured)."""
        if self._is_expired(key):
            return False
        return key in self._store

    async def delete(self, key: str) -> bool:
        """Delete a key.  Returns ``True`` if the key existed."""
        existed = key in self._store
        self._evict(key)
        return existed

    async def incr(self, key: str) -> int:
        """Increment the integer value of a key by 1.  Sets to 1 if absent."""
        if self._is_expired(key):
            pass  # already evicted
        self._assert_type(key, "string")
        current = self._store.get(key, "0")
        try:
            new_val = int(current) + 1
        except (ValueError, TypeError):
            raise ValueError(f"value at '{key}' is not an integer")
        self._store[key] = str(new_val)
        self._types[key] = "string"
        return new_val

    # ------------------------------------------------------------------
    # Expiry command
    # ------------------------------------------------------------------

    async def expire(self, key: str, ttl: int) -> bool:
        """Set a TTL on an existing key.  Returns ``True`` if the key exists."""
        if self._is_expired(key):
            return False
        if key not in self._store:
            return False
        self._expiries[key] = time.time() + ttl
        return True

    async def ttl(self, key: str) -> int:
        """Return remaining TTL in seconds.  -1 = no expiry, -2 = key missing."""
        if self._is_expired(key) or key not in self._store:
            return -2
        exp = self._expiries.get(key)
        if exp is None:
            return -1
        remaining = int(exp - time.time())
        return max(remaining, 0)

    # ------------------------------------------------------------------
    # Set commands
    # ------------------------------------------------------------------

    async def sadd(self, key: str, *members: str) -> int:
        """Add members to a set.  Returns the number of new members."""
        if self._is_expired(key):
            pass
        self._assert_type(key, "set")
        s: set[str] = self._store.setdefault(key, set())
        self._types[key] = "set"
        before = len(s)
        s.update(members)
        return len(s) - before

    async def sismember(self, key: str, member: str) -> bool:
        """Check if *member* is in the set at *key*."""
        if self._is_expired(key):
            return False
        self._assert_type(key, "set")
        s: set[str] = self._store.get(key, set())
        return member in s

    async def srem(self, key: str, *members: str) -> int:
        """Remove members from a set.  Returns the number removed."""
        if self._is_expired(key):
            return 0
        self._assert_type(key, "set")
        s: set[str] = self._store.get(key, set())
        removed = 0
        for m in members:
            if m in s:
                s.discard(m)
                removed += 1
        return removed

    async def smembers(self, key: str) -> set[str]:
        """Return all members of the set."""
        if self._is_expired(key):
            return set()
        self._assert_type(key, "set")
        return set(self._store.get(key, set()))

    # ------------------------------------------------------------------
    # Sorted-set commands
    # ------------------------------------------------------------------

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        """Add members with scores.  Returns number of *new* members."""
        if self._is_expired(key):
            pass
        self._assert_type(key, "zset")
        zset: dict[str, float] = self._store.setdefault(key, {})
        self._types[key] = "zset"
        added = 0
        for member, score in mapping.items():
            if member not in zset:
                added += 1
            zset[member] = score
        return added

    async def zrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> list[str]:
        """Return members with scores between *min_score* and *max_score*."""
        if self._is_expired(key):
            return []
        self._assert_type(key, "zset")
        zset: dict[str, float] = self._store.get(key, {})
        return sorted(
            (m for m, s in zset.items() if min_score <= s <= max_score),
            key=lambda m: zset[m],
        )

    async def zremrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> int:
        """Remove members with scores in ``[min_score, max_score]``."""
        if self._is_expired(key):
            return 0
        self._assert_type(key, "zset")
        zset: dict[str, float] = self._store.get(key, {})
        to_remove = [m for m, s in zset.items() if min_score <= s <= max_score]
        for m in to_remove:
            del zset[m]
        return len(to_remove)

    async def zcard(self, key: str) -> int:
        """Return the number of members in a sorted set."""
        if self._is_expired(key):
            return 0
        self._assert_type(key, "zset")
        return len(self._store.get(key, {}))

    # ------------------------------------------------------------------
    # Hash commands
    # ------------------------------------------------------------------

    async def hset(self, key: str, field: str, value: str) -> bool:
        """Set a field in a hash.  Returns ``True`` if the field is new."""
        if self._is_expired(key):
            pass
        self._assert_type(key, "hash")
        h: dict[str, str] = self._store.setdefault(key, {})
        self._types[key] = "hash"
        is_new = field not in h
        h[field] = value
        return is_new

    async def hget(self, key: str, field: str) -> str | None:
        """Get a single field from a hash."""
        if self._is_expired(key):
            return None
        self._assert_type(key, "hash")
        h: dict[str, str] = self._store.get(key, {})
        return h.get(field)

    async def hgetall(self, key: str) -> dict[str, str]:
        """Return all field→value pairs in a hash."""
        if self._is_expired(key):
            return {}
        self._assert_type(key, "hash")
        return dict(self._store.get(key, {}))

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def pipeline(self) -> CachePipeline:
        """Return a pipeline that batches commands and executes together."""
        return CachePipeline(self)


class CachePipeline:
    """Batches cache commands and executes them sequentially.

    Mirrors the Redis pipeline API for code compatibility.
    """

    def __init__(self, cache: InMemoryCache) -> None:
        self._cache = cache
        self._commands: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    # Each method simply records the call
    def get(self, key: str) -> CachePipeline:
        self._commands.append(("get", (key,), {}))
        return self

    def set(self, key: str, value: str, ttl: int | None = None) -> CachePipeline:
        self._commands.append(("set", (key, value), {"ttl": ttl}))
        return self

    def delete(self, key: str) -> CachePipeline:
        self._commands.append(("delete", (key,), {}))
        return self

    def exists(self, key: str) -> CachePipeline:
        self._commands.append(("exists", (key,), {}))
        return self

    def incr(self, key: str) -> CachePipeline:
        self._commands.append(("incr", (key,), {}))
        return self

    def sadd(self, key: str, *members: str) -> CachePipeline:
        self._commands.append(("sadd", (key, *members), {}))
        return self

    def sismember(self, key: str, member: str) -> CachePipeline:
        self._commands.append(("sismember", (key, member), {}))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> CachePipeline:
        self._commands.append(("zadd", (key, mapping), {}))
        return self

    def zrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> CachePipeline:
        self._commands.append(("zrangebyscore", (key, min_score, max_score), {}))
        return self

    def expire(self, key: str, ttl: int) -> CachePipeline:
        self._commands.append(("expire", (key, ttl), {}))
        return self

    def hset(self, key: str, field: str, value: str) -> CachePipeline:
        self._commands.append(("hset", (key, field, value), {}))
        return self

    def hget(self, key: str, field: str) -> CachePipeline:
        self._commands.append(("hget", (key, field), {}))
        return self

    def hgetall(self, key: str) -> CachePipeline:
        self._commands.append(("hgetall", (key,), {}))
        return self

    async def execute(self) -> list[Any]:
        """Execute all queued commands in order and return results."""
        results: list[Any] = []
        for method_name, args, kwargs in self._commands:
            method = getattr(self._cache, method_name)
            result = await method(*args, **kwargs)
            results.append(result)
        self._commands.clear()
        return results

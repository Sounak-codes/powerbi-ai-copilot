"""
Persistent memory store with Redis-backed caching.

Provides a unified interface for storing and retrieving conversation
memory, session data, and context across restarts. Falls back to
in-memory storage when Redis is unavailable.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)

# Try Redis — gracefully degrade to in-memory
try:
    import redis

    _redis_available = True
except ImportError:
    _redis_available = False


class PersistentMemoryStore:
    """
    Persistent memory store with optional Redis backend.

    Falls back to in-memory dict when Redis is not configured or available.
    Used for:
    - Persisting conversation history across server restarts
    - Sharing state across workers
    - TTL-based auto-cleanup
    """

    def __init__(self, prefix: str = "pbi_copilot"):
        self.prefix = prefix
        self._memory: Dict[str, Any] = {}  # In-memory fallback
        self._redis_client: Optional[Any] = None

        if _redis_available and settings.redis_url:
            try:
                self._redis_client = redis.from_url(
                    settings.redis_url, decode_responses=True
                )
                self._redis_client.ping()
                logger.info("Connected to Redis for persistent memory")
            except Exception as e:
                logger.warning(f"Redis unavailable, using in-memory store: {e}")
                self._redis_client = None
        else:
            logger.info("Redis not configured — using in-memory memory store")

    @property
    def is_persistent(self) -> bool:
        """Check if we have a persistent backend."""
        return self._redis_client is not None

    def _key(self, namespace: str, key: str) -> str:
        """Build a namespaced key."""
        return f"{self.prefix}:{namespace}:{key}"

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Store a value.

        Args:
            namespace: Logical namespace (e.g., "conversation", "session").
            key: Unique key within the namespace.
            value: Value to store (must be JSON-serializable).
            ttl_seconds: Optional TTL — auto-deletes after this many seconds.

        Returns:
            True if stored successfully.
        """
        full_key = self._key(namespace, key)

        try:
            serialized = json.dumps(value, default=str)

            if self._redis_client:
                if ttl_seconds:
                    self._redis_client.setex(full_key, ttl_seconds, serialized)
                else:
                    self._redis_client.set(full_key, serialized)
            else:
                self._memory[full_key] = {
                    "value": serialized,
                    "expires_at": (
                        datetime.utcnow() + timedelta(seconds=ttl_seconds)
                        if ttl_seconds
                        else None
                    ),
                }

            return True

        except Exception as e:
            logger.error(f"Failed to store {full_key}: {e}")
            return False

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Retrieve a value.

        Returns:
            Deserialized value, or None if not found / expired.
        """
        full_key = self._key(namespace, key)

        try:
            if self._redis_client:
                raw = self._redis_client.get(full_key)
                if raw is None:
                    return None
                return json.loads(raw)
            else:
                entry = self._memory.get(full_key)
                if entry is None:
                    return None

                # Check TTL for in-memory
                expires_at = entry.get("expires_at")
                if expires_at and datetime.utcnow() > expires_at:
                    del self._memory[full_key]
                    return None

                return json.loads(entry["value"])

        except Exception as e:
            logger.error(f"Failed to get {full_key}: {e}")
            return None

    def delete(self, namespace: str, key: str) -> bool:
        """Delete a value."""
        full_key = self._key(namespace, key)

        try:
            if self._redis_client:
                return self._redis_client.delete(full_key) > 0
            else:
                if full_key in self._memory:
                    del self._memory[full_key]
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete {full_key}: {e}")
            return False

    def exists(self, namespace: str, key: str) -> bool:
        """Check if a key exists."""
        full_key = self._key(namespace, key)

        if self._redis_client:
            return bool(self._redis_client.exists(full_key))
        return full_key in self._memory

    def list_keys(self, namespace: str) -> List[str]:
        """List all keys in a namespace."""
        pattern = self._key(namespace, "*")

        if self._redis_client:
            full_keys = self._redis_client.keys(pattern)
            prefix_len = len(self._key(namespace, ""))
            return [k[prefix_len:] for k in full_keys]
        else:
            prefix = self._key(namespace, "")
            return [
                k[len(prefix):]
                for k in self._memory.keys()
                if k.startswith(prefix)
            ]

    def cleanup_expired(self) -> int:
        """Remove expired entries (only needed for in-memory mode)."""
        if self._redis_client:
            return 0  # Redis handles TTL natively

        now = datetime.utcnow()
        expired_keys = [
            k
            for k, v in self._memory.items()
            if v.get("expires_at") and now > v["expires_at"]
        ]

        for k in expired_keys:
            del self._memory[k]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired memory entries")

        return len(expired_keys)

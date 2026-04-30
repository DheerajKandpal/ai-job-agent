import time


_CACHE: dict[str, tuple[object, float | None]] = {}


def get(key: str):
    item = _CACHE.get(key)
    if item is None:
        return None

    value, expires_at = item
    if expires_at is not None and time.time() > expires_at:
        _CACHE.pop(key, None)
        return None

    return value


def set(key: str, value, ttl: int | None = None) -> None:
    expires_at = time.time() + ttl if ttl is not None else None
    _CACHE[key] = (value, expires_at)

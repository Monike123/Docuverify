"""Round-robin Gemini API key pool with failover on quota/rate-limit errors."""

from __future__ import annotations

import logging
import threading
from datetime import date
from typing import Callable, TypeVar

logger = logging.getLogger("docverify.gemini.keys")

T = TypeVar("T")

_lock = threading.Lock()
_index = 0
_daily_counts: dict[str, int] = {}
_daily_date: date | None = None

# Soft warning threshold per key per day (Gemini 3 Flash free ~20 RPD)
DAILY_WARN_THRESHOLD = 15

_RETRYABLE_MARKERS = (
    "429",
    "resource exhausted",
    "quota",
    "rate limit",
    "too many requests",
    "exceeded",
)


def get_api_keys() -> list[str]:
    from config import GEMINI_API_KEY, GEMINI_API_KEYS

    keys = list(GEMINI_API_KEYS)
    if GEMINI_API_KEY and GEMINI_API_KEY not in keys:
        keys.insert(0, GEMINI_API_KEY)
    return [k for k in keys if k]


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def _bump_usage(key: str) -> None:
    global _daily_date
    today = date.today()
    with _lock:
        if _daily_date != today:
            _daily_counts.clear()
            _daily_date = today
        _daily_counts[key] = _daily_counts.get(key, 0) + 1
        count = _daily_counts[key]
        if count >= DAILY_WARN_THRESHOLD:
            logger.warning("Gemini key %s at %d requests today (free tier limit ~20/day)", _mask_key(key), count)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _RETRYABLE_MARKERS)


def call_with_failover(fn: Callable[[str], T]) -> tuple[T | None, int | None, Exception | None]:
    """Try each API key in round-robin order. Returns (result, key_index, last_error)."""
    keys = get_api_keys()
    if not keys:
        return None, None, ValueError("No Gemini API keys configured")

    global _index
    with _lock:
        start = _index % len(keys)
        _index += 1

    last_error: Exception | None = None
    for offset in range(len(keys)):
        key_idx = (start + offset) % len(keys)
        key = keys[key_idx]
        try:
            result = fn(key)
            _bump_usage(key)
            return result, key_idx, None
        except Exception as exc:
            last_error = exc
            if _is_retryable(exc) and offset < len(keys) - 1:
                logger.warning("Gemini key %s failed (%s), trying next key", _mask_key(key), exc)
                continue
            logger.warning("Gemini key %s failed: %s", _mask_key(key), exc)
            return None, key_idx, exc

    return None, None, last_error

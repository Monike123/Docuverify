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

# gemini-3-flash free tier: 1000 RPD per key; warn at 90% usage
DAILY_WARN_THRESHOLD = 900

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
    """Try each API key in round-robin order. Returns (result, key_index, last_error).

    On quota/rate-limit errors: cycles through ALL remaining keys before failing.
    On non-retryable errors: fails immediately (wrong API key, invalid request, etc.).
    """
    keys = get_api_keys()
    if not keys:
        return None, None, ValueError("No Gemini API keys configured")

    global _index
    with _lock:
        start = _index % len(keys)
        _index = (_index + 1) % len(keys)

    last_error: Exception | None = None
    tried: list[int] = []

    for offset in range(len(keys)):
        key_idx = (start + offset) % len(keys)
        key = keys[key_idx]
        tried.append(key_idx)
        try:
            result = fn(key)
            _bump_usage(key)
            logger.debug("Gemini call succeeded with key %d/%d", key_idx + 1, len(keys))
            return result, key_idx, None
        except Exception as exc:
            last_error = exc
            if _is_retryable(exc):
                logger.warning(
                    "Gemini key %d/%d quota/rate-limit (%s), trying next",
                    key_idx + 1, len(keys), _mask_key(key)
                )
                continue
            # Non-retryable (bad key, invalid request, etc.) — fail fast
            logger.warning("Gemini key %d/%d non-retryable error: %s", key_idx + 1, len(keys), exc)
            return None, key_idx, exc

    logger.error("All %d Gemini keys exhausted. Last error: %s", len(keys), last_error)
    return None, None, last_error

"""Process-local spend admission for the documented single-API deployment."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from threading import Lock
import logging
import time

from fastapi import HTTPException, status

from app.config import settings


logger = logging.getLogger(__name__)


class UsageClass(StrEnum):
    DOCUMENT_INGESTION = "document_ingestion"
    PROVIDER_GENERATION = "provider_generation"
    ASK_LUCENT = "ask_lucent"


@dataclass(frozen=True)
class LimitPolicy:
    user_limit: int | None
    global_limit: int
    window_seconds: int


@dataclass
class _Counter:
    window: int
    count: int
    expires_at: float


class FixedWindowLimiter:
    """Atomically enforce user and process-global limits in one fixed window."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, str], _Counter] = {}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()

    def consume(
        self,
        usage_class: UsageClass,
        *,
        user_key: str | None,
        policy: LimitPolicy,
        now: float | None = None,
    ) -> None:
        current = time.monotonic() if now is None else now
        window = int(current // policy.window_seconds)
        retry_after = max(1, ceil(((window + 1) * policy.window_seconds) - current))
        keys = [(usage_class.value, "global")]
        limits = [policy.global_limit]
        if user_key is not None and policy.user_limit is not None:
            keys.append((usage_class.value, f"user:{user_key}"))
            limits.append(policy.user_limit)

        with self._lock:
            expired = [key for key, counter in self._counters.items() if counter.expires_at <= current]
            for key in expired:
                del self._counters[key]
            counters = []
            for key in keys:
                counter = self._counters.get(key)
                if counter is None or counter.window != window:
                    counter = _Counter(
                        window=window,
                        count=0,
                        expires_at=(window + 1) * policy.window_seconds,
                    )
                    self._counters[key] = counter
                counters.append(counter)
            denied_scope = next(
                (
                    "global" if index == 0 else "user"
                    for index, (counter, limit) in enumerate(zip(counters, limits))
                    if counter.count >= limit
                ),
                None,
            )
            if denied_scope is None:
                for counter in counters:
                    counter.count += 1
                return

        logger.warning(
            "usage_limit_reached usage_class=%s scope=%s retry_after_seconds=%s",
            usage_class.value,
            denied_scope,
            retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "usage_limit_reached",
                "message": "Lucent has reached a temporary usage limit. Please try again later.",
                "limitClass": usage_class.value,
            },
            headers={"Retry-After": str(retry_after)},
        )


limiter = FixedWindowLimiter()


def policy_for(usage_class: UsageClass) -> LimitPolicy:
    if usage_class == UsageClass.DOCUMENT_INGESTION:
        return LimitPolicy(settings.usage_ingestion_user_limit, settings.usage_ingestion_global_limit, 3600)
    if usage_class == UsageClass.PROVIDER_GENERATION:
        return LimitPolicy(settings.usage_generation_user_limit, settings.usage_generation_global_limit, 3600)
    return LimitPolicy(settings.usage_ask_user_limit, settings.usage_ask_global_limit, settings.usage_ask_window_seconds)


def enforce_usage_limit(usage_class: UsageClass, user_id: object) -> None:
    limiter.consume(usage_class, user_key=str(user_id), policy=policy_for(usage_class))


def enforce_global_usage_limit(usage_class: UsageClass) -> None:
    policy = policy_for(usage_class)
    limiter.consume(
        usage_class,
        user_key=None,
        policy=LimitPolicy(user_limit=None, global_limit=policy.global_limit, window_seconds=policy.window_seconds),
    )

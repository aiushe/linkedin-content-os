"""Failure taxonomy and small retry primitives for the content harness."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

from . import config


class FailureClass(str, Enum):
    TRANSIENT = "transient"
    DEGRADABLE = "degradable"
    CAPABILITY = "capability"
    INTEGRITY = "integrity"
    LOOP = "loop"


@dataclass
class AgentFailure(Exception):
    failure_class: FailureClass
    message: str
    detail: str | None = None

    def as_record(self, *, node: str) -> dict[str, str]:
        return {
            "node": node,
            "class": self.failure_class.value,
            "message": self.message,
            "detail": self.detail or "",
        }


def retry_delay(attempt: int) -> float:
    """Return exponential backoff in seconds for a zero-indexed retry attempt."""

    return config.RETRY_BASE_DELAY * (2**attempt)


def should_retry(failure: AgentFailure, attempt: int) -> bool:
    return failure.failure_class == FailureClass.TRANSIENT and attempt < config.RETRY_MAX


T = TypeVar("T")


def with_retry(operation: Callable[[], T], *, sleep: Callable[[float], None] = time.sleep) -> T:
    """Retry only transient failures; all other classes return control immediately."""

    attempt = 0
    while True:
        try:
            return operation()
        except AgentFailure as failure:
            if not should_retry(failure, attempt):
                raise
            sleep(retry_delay(attempt))
            attempt += 1

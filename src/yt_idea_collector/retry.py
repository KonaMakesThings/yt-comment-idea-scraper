from __future__ import annotations

import random
import socket
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def with_retry(call: Callable[[], T], *, attempts: int = 5, base_delay: float = 1.0) -> T:
    """Retry transient Google errors and rate limits without swallowing final failures."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            text = str(exc).lower()
            transient = (isinstance(exc, (TimeoutError, socket.timeout, ConnectionError))
                         or status in {408, 429, 500, 502, 503, 504}
                         or any(token in text for token in (
                             "resource_exhausted", "rate limit", "temporarily unavailable",
                             "timed out", "timeout", "connection reset", "remote end closed",
                         )))
            if not transient or attempt == attempts - 1:
                raise
            time.sleep(base_delay * (2**attempt) + random.random())
    raise AssertionError("unreachable")

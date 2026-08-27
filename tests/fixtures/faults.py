"""Named environment switches for predictable live-demo fault injection.

Set one of these before a run: FAULT_SEARCH_500, FAULT_EMPTY_INDEX,
FAULT_SLOW_TOOL, or FAULT_FORCE_UNGROUNDED.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def injected(name: str) -> Iterator[None]:
    previous = os.getenv(name)
    os.environ[name] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous

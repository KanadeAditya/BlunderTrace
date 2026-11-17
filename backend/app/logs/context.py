"""Fields that ride along with every log line, such as the request id.

A `ContextVar` is Python's version of Node's `AsyncLocalStorage`: a value that belongs to the
current request (or job) and follows it across `await`s, without being passed to every function.
Two requests handled at the same time each see their own value.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_fields: ContextVar[dict[str, Any] | None] = ContextVar("log_fields", default=None)


def current_context() -> dict[str, Any]:
    """The fields bound right now (a copy, safe to change)."""
    return dict(_fields.get() or {})


@contextmanager
def bind(**fields: Any) -> Iterator[None]:
    """Add fields to every log line inside the `with` block, e.g. `with bind(report_id=rid):`."""
    token = _fields.set({**(_fields.get() or {}), **fields})
    try:
        yield
    finally:
        _fields.reset(token)

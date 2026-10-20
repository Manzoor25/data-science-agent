"""Request-local progress events. Version 1 shows working state in the browser."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

ProgressReporter = Callable[[dict[str, Any]], None]
_REPORTER: ContextVar[ProgressReporter | None] = ContextVar("progress_reporter", default=None)


@contextmanager
def progress_reporter(reporter: ProgressReporter | None) -> Iterator[None]:
    token = _REPORTER.set(reporter)
    try:
        yield
    finally:
        _REPORTER.reset(token)


def report_progress(stage: str, message: str, **details: Any) -> None:
    reporter = _REPORTER.get()
    if reporter is not None:
        reporter({"type": "progress", "stage": stage, "message": message, **details})

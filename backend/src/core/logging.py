"""Logging setup and latency profiler."""

import inspect
import json
import logging
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any, TextIO, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# Standard LogRecord attributes to ignore when extracting custom extra fields
STANDARD_RECORD_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
}


class JSONFormatter(logging.Formatter):
    """Single-line ISO-8601 JSON formatter for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Pull custom extra kwargs passed by callers
        for key, val in record.__dict__.items():
            if key not in STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = val

        return json.dumps(payload, default=str)


class StandardFormatter(logging.Formatter):
    """Readable format for local terminal dev."""

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt=self.DATE_FORMAT)


def configure_logging(
    level: str | None = None,
    json_format: bool = False,
    stream: TextIO | None = None,
) -> None:
    resolved_level = getattr(logging, (level or "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(resolved_level)

    while root.handlers:
        root.handlers.pop()

    target_stream = stream or sys.stderr
    handler = logging.StreamHandler(target_stream)
    # NOTSET allows sub-loggers set to DEBUG to pass through even if root is INFO
    handler.setLevel(logging.NOTSET)
    handler.setFormatter(JSONFormatter() if json_format else StandardFormatter())
    root.addHandler(handler)

    # quiet noisy third-party libraries
    for name in ["urllib3", "watchdog", "pypdf", "neo4j", "httpcore", "httpx"]:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def profile_stage(stage_name: str | None = None) -> Callable[[F], F]:
    """Logs start, completion, and duration in ms for sync and async functions."""

    def decorator(func: F) -> F:
        label = stage_name or func.__name__
        logger = logging.getLogger(func.__module__)

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                logger.debug(f"[{label}] starting")
                try:
                    result = await func(*args, **kwargs)
                    ms = (time.perf_counter() - start) * 1000.0
                    logger.info(f"[{label}] finished in {ms:.2f} ms")
                    return result
                except Exception as exc:
                    ms = (time.perf_counter() - start) * 1000.0
                    logger.error(f"[{label}] failed after {ms:.2f} ms: {exc}", exc_info=True)
                    raise

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            logger.debug(f"[{label}] starting")
            try:
                result = func(*args, **kwargs)
                ms = (time.perf_counter() - start) * 1000.0
                logger.info(f"[{label}] finished in {ms:.2f} ms")
                return result
            except Exception as exc:
                ms = (time.perf_counter() - start) * 1000.0
                logger.error(f"[{label}] failed after {ms:.2f} ms: {exc}", exc_info=True)
                raise

        return sync_wrapper  # type: ignore[return-value]

    return decorator

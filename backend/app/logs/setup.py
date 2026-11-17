"""Turns Python's standard logging into one JSON object per line."""

import json
import logging
import sys
from datetime import UTC, datetime

from app.logs.context import current_context

# Attributes every LogRecord has. Anything else on a record came from `extra={...}` and is logged
# as its own field. ("color_message" is uvicorn's copy of the message with terminal colours.)
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "taskName",
    "color_message",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        line.update(current_context())
        line.update({k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS})
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def setup_logging(service: str, level: str = "INFO") -> None:
    """Send every log line, ours and the libraries', to stdout as JSON. Safe to call twice."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # uvicorn has its own handlers; route its lines through ours instead.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    # We log one access line per request ourselves, with the request id, so uvicorn's is off.
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False

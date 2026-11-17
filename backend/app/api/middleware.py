"""Runs around every request: gives it an id, logs one line about it, and catches crashes.

Like an Express middleware `(req, res, next) => {...}` registered with `app.use`, but async:
`await call_next(request)` runs the route, and the code after it runs on the way back out.
"""

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.errors import INTERNAL_ERROR_DETAIL, error_response
from app.logs import bind

log = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
# A caller may send its own id (handy for tracing). Only short, plain ids are kept, so a crafted
# header can't inject fake content into the logs.
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _request_id(request: Request) -> str:
    sent = request.headers.get(REQUEST_ID_HEADER, "")
    return sent if _SAFE_ID.match(sent) else uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_id(request)
        started = time.perf_counter()
        with bind(request_id=request_id):
            try:
                response = await call_next(request)
            except Exception:
                # Anything unexpected: full details go to the log, the visitor gets a short
                # message in the usual error shape (never a stack trace).
                log.exception("unhandled error", extra={"path": request.url.path})
                response = error_response(500, "internal_error", INTERNAL_ERROR_DETAIL)
            response.headers[REQUEST_ID_HEADER] = request_id
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
        return response

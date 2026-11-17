"""One error shape everywhere: `{"error": "<code>", "detail": "<sentence for humans>"}`.

The frontend shows `detail` as is, so it is always a readable sentence and never a stack trace.
The codes are listed in docs/API.md ("Errors").
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

INTERNAL_ERROR_DETAIL = "Something went wrong on our side. Please try again."


class AppError(Exception):
    """An expected failure with its HTTP status, e.g. AppError(404, "report_not_found", "...")."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def error_response(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "detail": detail})


def _validation_detail(exc: RequestValidationError) -> str:
    """FastAPI's list of problems → one sentence, e.g. "games: Input should be 10, 20, 30 or 50"."""
    first = exc.errors()[0]
    where = ".".join(
        str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path")
    )
    message = first.get("msg", "Invalid input")
    return f"{where}: {message}" if where else message


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default 422 body is {"detail": [...]}; convert it to our shape.
        return error_response(422, "invalid_input", _validation_detail(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Raised by the framework itself, e.g. an unknown URL (404) or a wrong method (405).
        known = {
            404: ("not_found", "There's nothing at this address."),
            405: ("method_not_allowed", "This address doesn't accept that kind of request."),
        }
        code, detail = known.get(
            exc.status_code, ("http_error", "The request could not be handled.")
        )
        return error_response(exc.status_code, code, detail)

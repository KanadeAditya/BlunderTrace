"""One error shape everywhere: `{"error": "<code>", "detail": "<sentence for humans>"}`.

The frontend shows `detail` as is, so it is always a readable sentence and never a stack trace.
The codes are listed in docs/API.md ("Errors").
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.chesscom import ChesscomUnavailable, PlayerNotFound
from app.reports import TIME_LABELS, Busy, GameNotFound, NoGames, ReportNotFound

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

    @app.exception_handler(PlayerNotFound)
    async def player_not_found(_: Request, exc: PlayerNotFound) -> JSONResponse:
        detail = f"No chess.com player called '{exc.username}'."
        return error_response(404, "username_not_found", detail)

    @app.exception_handler(ChesscomUnavailable)
    async def chesscom_unavailable(_: Request, exc: ChesscomUnavailable) -> JSONResponse:
        log.warning("chess.com unavailable", extra={"reason": str(exc)})
        detail = "chess.com isn't responding right now. Please try again in a minute."
        return error_response(503, "chesscom_unavailable", detail)

    @app.exception_handler(NoGames)
    async def no_games(_: Request, exc: NoGames) -> JSONResponse:
        label = TIME_LABELS[exc.time_control]
        hint = "" if exc.time_control == "both" else " Try 'Both'."
        return error_response(422, "no_games", f"No {label} games found for {exc.username}.{hint}")

    @app.exception_handler(Busy)
    async def busy(_: Request, exc: Busy) -> JSONResponse:
        detail = "BlunderTrace is busy right now. Please try again in a few minutes."
        return error_response(503, "busy", detail)

    @app.exception_handler(ReportNotFound)
    async def report_not_found(_: Request, exc: ReportNotFound) -> JSONResponse:
        return error_response(404, "report_not_found", "No report with that id.")

    @app.exception_handler(GameNotFound)
    async def game_not_found(_: Request, exc: GameNotFound) -> JSONResponse:
        return error_response(404, "game_not_found", "No game with that id in this report.")

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

"""The HTTP layer: routes, request/response models (docs/API.md), errors and request ids.

No SQL and no chess here: routes check input, call into `app.reports` and shape the answer.
Nothing else in the app imports this folder.
"""

from fastapi import APIRouter

from app.api.errors import AppError, install_error_handlers
from app.api.health import router as health_router
from app.api.middleware import RequestContextMiddleware

router = APIRouter()
router.include_router(health_router)

__all__ = ["AppError", "RequestContextMiddleware", "install_error_handlers", "router"]

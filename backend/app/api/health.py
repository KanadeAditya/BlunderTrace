"""`GET /health`: is everything this process depends on working?

Each build step adds its check here: the database (step 2), worker heartbeats (step 5) and the
library (step 6). The status is "healthy" when everything is OK, "degraded" when the API works but
something optional is missing (e.g. no worker alive), and "unhealthy" (HTTP 503) when the API can't
do its job.
"""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class Health(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    checks: dict[str, object]


@router.get("/health", response_model=Health)
async def health(response: Response) -> Health:
    checks: dict[str, object] = {}
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    if status == "unhealthy":
        response.status_code = 503
    return Health(status=status, version=get_settings().app_version, checks=checks)

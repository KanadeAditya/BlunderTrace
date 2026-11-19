"""`GET /api/players/{username}`: the Home page's player preview (docs/API.md, section 0)."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.reports import PlayerSummary, lookup_player

router = APIRouter(prefix="/api")

# chess.com usernames: letters, digits, "_" and "-", 3 to 25 characters.
Username = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{3,25}$")]


@router.get("/players/{username}", response_model=PlayerSummary)
async def get_player(username: Username) -> PlayerSummary:
    # Unknown player -> 404 username_not_found; chess.com down -> 503 (see errors.py).
    return await lookup_player(username)

"""Talking to chess.com's public API, politely and with a cache.

chess.com's rules for this API: one request at a time is never rate-limited (parallel requests may
get "429 Too Many Requests"), and apps should identify themselves in the User-Agent. Every answer is
cached in the `cache` table; once a cached answer expires, we ask again with its ETag, and a
"304 Not Modified" reply costs almost nothing.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
from pydantic import ValidationError

from app.chesscom.models import Archives, ChesscomGame, Stats
from app.db import cache_extend, cache_get, cache_put

log = logging.getLogger(__name__)

API = "https://api.chess.com/pub/player"
# Identifies the app with its public repository, never anyone's personal contact details.
USER_AGENT = "BlunderTrace/0.1 (+https://github.com/KanadeAditya/BlunderTrace)"

STATS_FOR = timedelta(minutes=5)  # the Home preview, while typing
ARCHIVE_LIST_FOR = timedelta(hours=1)  # the list of months
CURRENT_MONTH_FOR = timedelta(minutes=10)  # this month's games can still change
# Past months never change, so they are kept forever (None).


class PlayerNotFound(Exception):
    def __init__(self, username: str) -> None:
        super().__init__(f"no chess.com player called {username!r}")
        self.username = username


class ChesscomUnavailable(Exception):
    """chess.com didn't answer properly: a timeout, a 5xx, a 429, or broken JSON."""


class _NotFound(Exception):
    pass


class ChesscomClient:
    def __init__(self, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        self._http = httpx2.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
            follow_redirects=True,
            transport=transport,
        )
        self._one_at_a_time = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_json(self, url: str, keep_for: timedelta | None) -> Any:
        """GET a chess.com URL through the cache. `keep_for=None` caches it forever."""
        key = f"chesscom:{url}"
        cached = await cache_get(key)
        if cached is not None and cached.fresh:
            return cached.value

        headers = {"If-None-Match": cached.etag} if cached and cached.etag else {}
        async with self._one_at_a_time:
            try:
                response = await self._http.get(url, headers=headers)
            except httpx2.HTTPError as exc:
                raise ChesscomUnavailable(f"{type(exc).__name__} for {url}") from exc

        if response.status_code == 304 and cached is not None:
            await cache_extend(key, keep_for)
            return cached.value
        if response.status_code == 404:
            raise _NotFound(url)
        if response.status_code != 200:
            raise ChesscomUnavailable(f"HTTP {response.status_code} for {url}")
        try:
            value = response.json()
        except ValueError as exc:
            raise ChesscomUnavailable(f"invalid JSON from {url}") from exc
        await cache_put(key, value, keep_for, response.headers.get("etag"))
        return value


_client: ChesscomClient | None = None


def open_client(transport: httpx2.AsyncBaseTransport | None = None) -> ChesscomClient:
    """Create the shared client (tests pass a fake transport so nothing reaches chess.com)."""
    global _client
    if _client is None:
        _client = ChesscomClient(transport)
    return _client


def get_client() -> ChesscomClient:
    if _client is None:
        raise RuntimeError("chess.com client is not open (open_client() runs at startup)")
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def fetch_stats(username: str) -> Stats:
    try:
        data = await get_client().get_json(f"{API}/{username.lower()}/stats", STATS_FOR)
    except _NotFound:
        raise PlayerNotFound(username) from None
    try:
        return Stats.model_validate(data)
    except ValidationError as exc:
        raise ChesscomUnavailable("unexpected stats shape") from exc


async def fetch_archive_urls(username: str) -> list[str]:
    """The player's monthly archive links, oldest first, as chess.com lists them."""
    url = f"{API}/{username.lower()}/games/archives"
    try:
        data = await get_client().get_json(url, ARCHIVE_LIST_FOR)
    except _NotFound:
        raise PlayerNotFound(username) from None
    return Archives.model_validate(data).archives


def month_of(archive_url: str) -> tuple[int, int]:
    """ ".../games/2026/11" -> (2026, 11)."""
    year, month = archive_url.rstrip("/").split("/")[-2:]
    return int(year), int(month)


async def fetch_month(archive_url: str, now: datetime | None = None) -> list[ChesscomGame]:
    """One month of games. Games that don't fit the expected shape are skipped and logged."""
    now = now or datetime.now(UTC)
    current = month_of(archive_url) >= (now.year, now.month)
    keep_for = CURRENT_MONTH_FOR if current else None
    try:
        data = await get_client().get_json(archive_url, keep_for)
    except _NotFound:
        return []
    games: list[ChesscomGame] = []
    for raw in data.get("games", []) if isinstance(data, dict) else []:
        try:
            games.append(ChesscomGame.model_validate(raw))
        except ValidationError:
            log.warning(
                "skipped a chess.com game with an unexpected shape", extra={"month": archive_url}
            )
    return games

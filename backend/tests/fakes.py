"""Fakes shared by the tests: a fake chess.com that answers from saved real responses."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parent / "fixtures" / "chesscom"
NOW = datetime(2026, 11, 18, tzinfo=UTC)
BASE = "/pub/player/gothamchess"
MONTH = "https://api.chess.com/pub/player/gothamchess/games/2026/{:02d}"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def rapid_copies(games: list[dict], month: int) -> list[dict]:
    """The November blitz games, re-dated into another month as rapid games."""
    copies = []
    for i, game in enumerate(copy.deepcopy(games)):
        game["time_class"] = "rapid"
        game["url"] = f"https://www.chess.com/game/live/{month}00{i}"
        game["end_time"] -= (11 - month) * 30 * 86_400
        copies.append(game)
    return copies


class FakeChesscom:
    """Answers like chess.com: JSON with an ETag, 304 when the ETag matches, 404 when unknown."""

    def __init__(self) -> None:
        november = load("gothamchess_month.json")
        self.routes: dict[str, dict] = {
            f"{BASE}/stats": load("gothamchess_stats.json"),
            f"{BASE}/games/archives": load("gothamchess_archives.json"),
            f"{BASE}/games/2026/11": november,
            f"{BASE}/games/2026/10": {"games": rapid_copies(november["games"], 10)},
            f"{BASE}/games/2026/09": {"games": []},
        }
        self.requests: list[httpx2.Request] = []
        self.fail_with: int | Exception | None = None

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if isinstance(self.fail_with, Exception):
            raise self.fail_with
        if self.fail_with:
            return httpx2.Response(self.fail_with)
        body = self.routes.get(request.url.path)
        if body is None:
            return httpx2.Response(404, json={"code": 0, "message": "not found"})
        etag = f'"{hash(json.dumps(body, sort_keys=True))}"'
        if request.headers.get("if-none-match") == etag:
            return httpx2.Response(304)
        return httpx2.Response(200, json=body, headers={"ETag": etag})

    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests]

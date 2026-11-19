"""chess.com client, cache and game selection, against a fake chess.com built from saved responses.

No test ever reaches the real chess.com: the client is given a MockTransport that answers from the
JSON files in tests/fixtures/chesscom (real GothamChess responses, trimmed).
"""

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.chesscom import (
    ChesscomUnavailable,
    PlayerNotFound,
    close_client,
    open_client,
    recent_games,
)
from app.chesscom.client import USER_AGENT, fetch_month
from app.chesscom.select import months_to_search
from app.main import app
from app.reports import lookup_player
from tests.fakes import BASE, MONTH, NOW, FakeChesscom


@pytest.fixture
async def fake(db):
    server = FakeChesscom()
    open_client(httpx2.MockTransport(server.handle))
    yield server
    await close_client()


# --- player lookup ---------------------------------------------------------------------------


async def test_lookup_reads_ratings_and_all_time_game_counts(fake):
    player = await lookup_player("GothamChess")
    assert player.username == "gothamchess"
    assert player.ratings == {"rapid": 2453, "blitz": 2898}
    assert player.games == {"rapid": 96 + 17 + 4, "blitz": 10601 + 6401 + 1283}


async def test_requests_identify_the_app(fake):
    await lookup_player("gothamchess")
    assert fake.requests[0].headers["user-agent"] == USER_AGENT


async def test_a_second_lookup_comes_from_the_cache(fake):
    await lookup_player("gothamchess")
    await lookup_player("GOTHAMCHESS")  # any capitals: same player, same cache entry
    assert fake.paths() == [f"{BASE}/stats"]


async def test_an_expired_entry_is_rechecked_with_its_etag(fake, db):
    await lookup_player("gothamchess")
    async with db.connection() as conn:
        await conn.execute("UPDATE cache SET expires_at = now() - interval '1 second'")
    player = await lookup_player("gothamchess")
    assert player.ratings["blitz"] == 2898
    assert fake.requests[-1].headers.get("if-none-match")  # asked "has it changed?"
    async with db.connection() as conn:
        row = await (await conn.execute("SELECT expires_at > now() AS fresh FROM cache")).fetchone()
    assert row["fresh"]  # the 304 made the cached answer fresh again


async def test_unknown_player(fake):
    with pytest.raises(PlayerNotFound):
        await lookup_player("zz-no-such-player")


@pytest.mark.parametrize("failure", [503, 429, httpx2.ReadTimeout("slow")])
async def test_chesscom_failures_become_unavailable(fake, failure):
    fake.fail_with = failure
    with pytest.raises(ChesscomUnavailable):
        await lookup_player("gothamchess")


# --- choosing games --------------------------------------------------------------------------


async def test_newest_games_first_and_stops_once_there_are_enough(fake):
    games = await recent_games("gothamchess", "blitz", 5, now=NOW)
    assert len(games) == 5
    assert [g.end_time for g in games] == sorted((g.end_time for g in games), reverse=True)
    assert f"{BASE}/games/2026/10" not in fake.paths()  # November alone had enough


async def test_walks_back_through_months_when_needed(fake):
    games = await recent_games("gothamchess", "rapid", 5, now=NOW)
    assert len(games) == 5 and {g.time_class for g in games} == {"rapid"}
    assert f"{BASE}/games/2026/10" in fake.paths()


async def test_both_mixes_rapid_and_blitz_newest_first(fake):
    games = await recent_games("gothamchess", "both", 12, now=NOW)
    assert {g.time_class for g in games} == {"rapid", "blitz"}
    assert games[0].time_class == "blitz"  # November's blitz is newer than October's rapid


async def test_fewer_games_than_asked_returns_what_exists(fake):
    games = await recent_games("gothamchess", "rapid", 50, now=NOW)
    assert 0 < len(games) < 50


async def test_variants_other_speeds_short_and_broken_games_are_skipped(fake):
    november = fake.routes[f"{BASE}/games/2026/11"]["games"]
    good = november[0]
    variant = {**good, "url": "https://www.chess.com/game/live/1", "rules": "chess960"}
    bullet = {**good, "url": "https://www.chess.com/game/live/2", "time_class": "bullet"}
    short = {**good, "url": "https://www.chess.com/game/live/3", "pgn": "1. e4 e5 2. Qh5 Nc6 1-0"}
    broken = {"url": "https://www.chess.com/game/live/4"}  # missing almost everything
    fake.routes[f"{BASE}/games/2026/11"] = {"games": [good, variant, bullet, short, broken]}
    games = await recent_games("gothamchess", "blitz", 10, now=NOW)
    urls = {g.url for g in games}
    assert good["url"] in urls
    assert not urls & {f"https://www.chess.com/game/live/{i}" for i in range(1, 5)}


async def test_past_months_are_cached_forever_and_this_month_briefly(fake, db):
    await fetch_month(MONTH.format(10), now=NOW)
    await fetch_month(MONTH.format(11), now=NOW)
    async with db.connection() as conn:
        rows = await (await conn.execute("SELECT key, expires_at FROM cache")).fetchall()
    expiry = {row["key"].rsplit("/", 1)[-1]: row["expires_at"] for row in rows}
    assert expiry["10"] is None  # October is over: it can never change
    assert expiry["11"] is not None  # November is still being played


def test_only_the_last_24_months_are_searched():
    urls = [MONTH.replace("2026", str(y)).format(m) for y in (2023, 2024, 2025) for m in (1, 12)]
    found = months_to_search(urls, NOW)
    assert found[0].endswith("2025/12")  # newest first
    assert all(not u.endswith(("2023/01", "2023/12", "2024/01")) for u in found)


# --- the API endpoint ------------------------------------------------------------------------


@pytest.fixture
def api_with_fake(database):
    server = FakeChesscom()
    open_client(httpx2.MockTransport(server.handle))  # startup keeps this client instead
    with TestClient(app) as client:
        yield client, server


def test_player_endpoint_returns_the_api_shape(api_with_fake):
    client, _ = api_with_fake
    response = client.get("/api/players/GothamChess")
    assert response.status_code == 200
    assert response.json() == {
        "username": "gothamchess",
        "ratings": {"rapid": 2453, "blitz": 2898},
        "games": {"rapid": 117, "blitz": 18285},
    }


def test_player_endpoint_errors(api_with_fake):
    client, server = api_with_fake
    missing = client.get("/api/players/nobody-here")
    assert missing.status_code == 404
    assert missing.json() == {
        "error": "username_not_found",
        "detail": "No chess.com player called 'nobody-here'.",
    }
    bad = client.get("/api/players/a!")  # "!" is not allowed in a chess.com username
    assert (bad.status_code, bad.json()["error"]) == (422, "invalid_input")
    server.fail_with = 503
    down = client.get("/api/players/someone-new")
    assert (down.status_code, down.json()["error"]) == (503, "chesscom_unavailable")

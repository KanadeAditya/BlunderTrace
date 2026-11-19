"""The report flow (build step 5): starting, preparing, analysing, the last-game check, building,
reading, the retry rules and the stuck-report repair.

Real database, real Stockfish (small search, a few short games), fake chess.com.
"""

import asyncio
import shutil
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx2
import pytest
from fastapi.testclient import TestClient

from app import jobs  # noqa: F401  (registers the tasks on the queue app)
from app.chesscom import PlayerNotFound, close_client, open_client
from app.config import get_settings
from app.db.queue import queue_app
from app.engine import start_engine, stop_engine
from app.jobs.tasks import PREPARE_RETRY, TemporaryErrors
from app.main import app
from app.reports import (
    Busy,
    NoGames,
    build_report,
    check_report_complete,
    get_game,
    get_report,
    give_up_on_game,
    repair_stuck_reports,
    start_report,
)
from tests.conftest import wipe_tables
from tests.fakes import BASE, FakeChesscom

pytestmark = pytest.mark.skipif(shutil.which("stockfish") is None, reason="Stockfish not installed")


@pytest.fixture
async def flow(db):
    """Everything a worker has: the pool (from `db`), a fake chess.com with 3 short blitz games,
    the job queue, and Stockfish at a small search size."""
    server = FakeChesscom()
    november = server.routes[f"{BASE}/games/2026/11"]["games"]
    server.routes[f"{BASE}/games/2026/11"] = {"games": november[-3:]}
    open_client(httpx2.MockTransport(server.handle))
    await queue_app.open_async()
    await start_engine("stockfish", nodes=20_000, hash_mb=16)
    yield server
    await stop_engine()
    await queue_app.close_async()
    await close_client()


async def run_worker() -> None:
    """Run every queued job until the queue is empty (like a worker that stops when idle)."""
    await queue_app.run_worker_async(
        wait=False, concurrency=1, install_signal_handlers=False, listen_notify=False
    )


async def jobs_of(db, task: str) -> list[dict]:
    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT status, args FROM procrastinate_jobs WHERE task_name = %s", (task,)
        )
        return await cursor.fetchall()


# --- starting a report ---------------------------------------------------------------------


async def test_start_rules(flow, db, monkeypatch):
    with pytest.raises(PlayerNotFound):
        await start_report("nobody-here", "blitz", 20)
    flow.routes[f"{BASE}/stats"] = {  # blitz only, never rapid
        "chess_blitz": {"last": {"rating": 2900}, "record": {"win": 10, "loss": 5, "draw": 1}}
    }
    with pytest.raises(NoGames):
        await start_report("gothamchess", "rapid", 20)

    first, status = await start_report("GothamChess", "blitz", 20)
    assert status == "queued" and first.startswith("r_")
    assert len(await jobs_of(db, "prepare_report")) == 1
    again, status = await start_report("gothamchess", "blitz", 20)  # any capitals: the same report
    assert (again, status) == (first, "queued")  # joined, no duplicate

    monkeypatch.setattr(get_settings(), "max_active_reports", 1)
    with pytest.raises(Busy):
        await start_report("gothamchess", "blitz", 10)  # a different request: refused while busy


async def test_a_recently_finished_identical_report_is_reused(flow, db):
    report_id, _ = await start_report("gothamchess", "blitz", 20)
    async with db.connection() as conn:
        await conn.execute(
            "UPDATE reports SET status = 'done', result = '{}', finished_at = now() WHERE id = %s",
            (report_id,),
        )
    assert await start_report("gothamchess", "blitz", 20) == (report_id, "done")


# --- the whole flow --------------------------------------------------------------------------


async def test_a_report_runs_end_to_end(flow, db):
    report_id, _ = await start_report("gothamchess", "blitz", 20)
    await run_worker()  # prepare -> analyse x3 -> build

    report = await get_report(report_id)
    assert report["status"] == "done"
    assert report["progress"] == {"done": 3, "total": 3}
    assert report["notes"] == ["Only 3 blitz games found; patterns may be weak."]
    assert report["summary"]["games"] == 3
    assert {g["status"] for g in report["games"]} == {"done"}
    first = report["games"][0]
    assert set(first) >= {
        "opponent",
        "result",
        "date",
        "color",
        "opening",
        "url",
        "errors",
        "trace",
    }
    assert len(first["trace"]) == first["plies"] + 1
    assert len(await jobs_of(db, "analyse_game")) == 3
    assert len(await jobs_of(db, "build_report")) == 1

    game = await get_game(report_id, first["id"])
    assert game["grading"] == "complete" and all(m["grade"] for m in game["moves"])
    user = game["user_color"]
    for move in game["moves"]:
        note = move["refutation_note"] or ""
        if move["color"] != user:  # the opponent's moves are never "your"
            assert " your " not in f" {note} "
    for card in report["weaknesses"]:
        assert 1 <= card["count"] <= 3 and card["examples"] and card["sources"]


async def test_games_are_shared_between_reports_and_analysed_once(flow, db):
    first, _ = await start_report("gothamchess", "blitz", 20)
    await run_worker()
    second, _ = await start_report("gothamchess", "blitz", 10)  # a different request, same games
    await run_worker()
    assert (await get_report(second))["status"] == "done"
    assert len(await jobs_of(db, "analyse_game")) == 3  # all from the first report


# --- the last-game check and failures --------------------------------------------------------


async def prepared(flow, db) -> tuple[str, list[str]]:
    """A running report with its 3 games linked but not analysed (the queue emptied by hand)."""
    report_id, _ = await start_report("gothamchess", "blitz", 20)
    from app.reports import prepare_report

    await prepare_report(report_id)
    async with db.connection() as conn:
        await conn.execute("DELETE FROM procrastinate_jobs")
        rows = await (
            await conn.execute(
                "SELECT game_id FROM report_games WHERE report_id = %s ORDER BY position",
                (report_id,),
            )
        ).fetchall()
    return report_id, [r["game_id"] for r in rows]


async def finish_games(db, game_ids: list[str]) -> None:
    async with db.connection() as conn:
        await conn.execute(
            "UPDATE games SET status = 'done', moves = '[]',"
            ' error_counts = \'{"white": {}, "black": {}}\' WHERE id = ANY(%s)',
            (game_ids,),
        )


async def test_two_workers_finishing_together_queue_the_build_once(flow, db):
    report_id, games = await prepared(flow, db)
    await finish_games(db, games)
    results = await asyncio.gather(*(check_report_complete(report_id) for _ in range(5)))
    assert any(results)
    assert len(await jobs_of(db, "build_report")) == 1


async def test_a_finished_report_is_never_rebuilt(flow, db):
    report_id, games = await prepared(flow, db)
    await finish_games(db, games)
    async with db.connection() as conn:
        await conn.execute(
            "UPDATE reports SET status = 'done', result = '{}' WHERE id = %s", (report_id,)
        )
    assert await check_report_complete(report_id) is False
    assert await jobs_of(db, "build_report") == []


async def test_a_game_that_keeps_failing_is_skipped_and_the_report_still_finishes(flow, db):
    report_id, games = await prepared(flow, db)
    await finish_games(db, games[1:])
    await give_up_on_game(games[0], "ValueError: odd game")
    await build_report(report_id)
    report = await get_report(report_id)
    assert report["status"] == "done"
    assert "1 game couldn't be analysed and was skipped." in report["notes"]


async def test_a_report_fails_when_most_games_fail(flow, db):
    report_id, games = await prepared(flow, db)
    for game_id in games[:2]:
        await give_up_on_game(game_id, "ValueError: odd game")
    await finish_games(db, games[2:])
    await build_report(report_id)
    report = await get_report(report_id)
    assert (report["status"], report["error"]) == ("failed", "analysis_failed")


async def test_a_stuck_report_gets_its_missing_work_queued(flow, db):
    report_id, games = await prepared(flow, db)
    await finish_games(db, games)
    async with db.connection() as conn:
        await conn.execute(
            "UPDATE reports SET updated_at = now() - interval '10 minutes' WHERE id = %s",
            (report_id,),
        )
    assert await repair_stuck_reports() == 1
    assert len(await jobs_of(db, "build_report")) == 1
    assert await repair_stuck_reports() == 0  # its build is now waiting: nothing to repair


def test_only_temporary_errors_are_retried():
    from app.chesscom import ChesscomUnavailable

    first_try, last_try = SimpleNamespace(attempts=0), SimpleNamespace(attempts=2)
    retry = PREPARE_RETRY.get_retry_decision(exception=ChesscomUnavailable(), job=first_try)
    wait = (retry.retry_at - datetime.now(UTC)).total_seconds()
    assert 4 < wait <= 5  # the first retry waits 5 seconds
    assert PREPARE_RETRY.get_retry_decision(exception=ChesscomUnavailable(), job=last_try) is None
    assert PREPARE_RETRY.get_retry_decision(exception=ValueError(), job=first_try) is None
    assert isinstance(PREPARE_RETRY, TemporaryErrors)


# --- the API ---------------------------------------------------------------------------------


@pytest.fixture
def api(database):
    wipe_tables()
    server = FakeChesscom()
    open_client(httpx2.MockTransport(server.handle))
    with TestClient(app) as client:
        yield client


def test_starting_a_report_through_the_api(api):
    started = api.post("/api/reports", json={"username": "gothamchess", "time_control": "blitz"})
    assert started.status_code == 202
    assert started.json()["status"] == "queued"
    joined = api.post("/api/reports", json={"username": "gothamchess", "time_control": "blitz"})
    assert (joined.status_code, joined.json()["id"]) == (202, started.json()["id"])
    report = api.get(f"/api/reports/{started.json()['id']}").json()
    assert report["status"] in ("queued", "running")
    assert "summary" not in report  # absent until done


def test_report_api_errors(api):
    bad = api.post(
        "/api/reports", json={"username": "gothamchess", "time_control": "blitz", "games": 7}
    )
    assert (bad.status_code, bad.json()["error"]) == (422, "invalid_input")
    extra = {"username": "gothamchess", "time_control": "blitz", "admin": True}
    assert api.post("/api/reports", json=extra).json()["error"] == "invalid_input"
    assert api.get("/api/reports/not-an-id").json()["error"] == "report_not_found"
    assert api.get("/api/reports/r_zzzzzzzzzz").status_code == 404
    assert (
        api.get("/api/reports/r_zzzzzzzzzz/games/g_zzzzzzzzzz").json()["error"] == "game_not_found"
    )

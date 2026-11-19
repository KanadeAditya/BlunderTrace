"""The tables and the rules Postgres itself enforces (docs/BACKEND.md, section 5)."""

import asyncio

import numpy as np
import pytest
from psycopg import errors

from app.db import prepare_database

TABLES = {
    "reports",
    "games",
    "report_games",
    "corpus_chunks",
    "concept_queries",
    "cache",
    "llm_calls",
}


async def add_report(conn, rid="r_aaaaaa", username="adityakanade", status="queued", **extra):
    columns = {
        "id": rid,
        "username": username,
        "time_control": "rapid",
        "games_requested": 20,
        "status": status,
        **extra,
    }
    names = ", ".join(columns)
    marks = ", ".join(["%s"] * len(columns))
    await conn.execute(f"INSERT INTO reports ({names}) VALUES ({marks})", list(columns.values()))


async def test_all_tables_exist(db):
    async with db.connection() as conn:
        rows = await conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        found = {row["table_name"] for row in await rows.fetchall()}
    assert TABLES <= found


async def test_startup_is_safe_to_run_twice_at_once(database):
    # The API and a worker starting together: the lock makes them take turns.
    await asyncio.gather(prepare_database(database), prepare_database(database))


async def test_a_valid_report_is_accepted_and_bad_values_are_not(db):
    async with db.connection() as conn:
        await add_report(conn)
        with pytest.raises(errors.CheckViolation):
            await add_report(conn, rid="r_bbbbbb", status="pending")  # not an allowed status
    async with db.connection() as conn:
        with pytest.raises(errors.CheckViolation):
            await add_report(conn, rid="r_cccccc", username="AdityaKanade")  # not lower-cased


async def test_only_one_active_report_per_identical_request(db):
    async with db.connection() as conn:
        await add_report(conn, rid="r_first1")
        with pytest.raises(errors.UniqueViolation):
            await add_report(conn, rid="r_second")
    async with db.connection() as conn:
        # Once the first one is done, the same request may start a new report.
        await conn.execute(
            "UPDATE reports SET status = 'done', result = '{}' WHERE id = 'r_first1'"
        )
        await add_report(conn, rid="r_third1")


async def test_failed_means_an_error_code_and_done_means_a_result(db):
    async with db.connection() as conn:
        with pytest.raises(errors.CheckViolation):
            await add_report(conn, status="failed")  # no error code
    async with db.connection() as conn:
        with pytest.raises(errors.CheckViolation):
            await add_report(conn, status="done")  # no result


async def test_updated_at_moves_on_every_update(db):
    # Two separate transactions: inside one transaction, Postgres's now() stays the same.
    async with db.connection() as conn:
        await add_report(conn)
        before = await (await conn.execute("SELECT updated_at FROM reports")).fetchone()
    await asyncio.sleep(0.01)
    async with db.connection() as conn:
        await conn.execute("UPDATE reports SET status = 'running'")
        after = await (await conn.execute("SELECT updated_at FROM reports")).fetchone()
    assert after["updated_at"] > before["updated_at"]


async def test_a_game_is_stored_once_per_chesscom_link(db):
    insert = (
        "INSERT INTO games (id, chesscom_url, white, black, result, time_class, played_at,"
        " start_fen, pgn, plies) VALUES (%s, %s, 'a', 'b', '1-0', 'rapid', now(), 'fen', 'pgn', 40)"
    )
    url = "https://www.chess.com/game/live/123456789"
    async with db.connection() as conn:
        await conn.execute(insert, ("g_aaaaaa", url))
        with pytest.raises(errors.UniqueViolation):
            await conn.execute(insert, ("g_bbbbbb", url))


async def test_library_tags_must_be_known_themes(db):
    insert = (
        "INSERT INTO corpus_chunks (id, source, title, url, text, tags, embedding)"
        " VALUES (%s, 'wikipedia', 'Fork (chess)', 'https://en.wikipedia.org/wiki/Fork_(chess)',"
        " 'A fork is a tactic...', %s, %s)"
    )
    vector = np.zeros(1536, dtype=np.float32)
    async with db.connection() as conn:
        await conn.execute(insert, ("w1", ["fork", "hangingPiece"], vector))
        with pytest.raises(errors.CheckViolation):
            await conn.execute(insert, ("w2", ["notATheme"], vector))


async def test_vectors_and_full_text_work(db):
    vector = np.zeros(1536, dtype=np.float32)
    vector[0] = 1.0
    async with db.connection() as conn:
        await conn.execute(
            "INSERT INTO corpus_chunks (id, source, title, url, text, embedding) VALUES"
            " ('w1', 'wikipedia', 'Pin (chess)', 'u', 'The pinned knight cannot move.', %s)",
            (vector,),
        )
        row = await (
            await conn.execute(
                "SELECT embedding <=> %s AS distance, tsv @@ plainto_tsquery('english', 'pins')"
                " AS matches FROM corpus_chunks",
                (vector,),
            )
        ).fetchone()
    assert row["distance"] == pytest.approx(0.0)  # same vector: cosine distance 0
    assert row["matches"] is True  # "pins" matches "pinned": same word stem

"""`analyse_game`: Stockfish over every position, then grades, named tactics, lines and note facts,
saved as JSON in the game's row. Then the last-game check for every running report with this game.

A game already done is skipped straight to the check (gap 6: a game queued twice is analysed once).
"""

import logging
import time

from psycopg.types.json import Jsonb

from app.analysis import GRADING_VERSION, PositionEval, capped_cp, parse_pgn
from app.analysis import analyse_game as grade_game
from app.db import get_pool
from app.engine import Position, get_engine
from app.logs import bind
from app.reports.complete import check_reports_of_game

log = logging.getLogger(__name__)

TRACE_EVERY = 10  # the Analysing screen's trace grows every 10 positions

_SAVE = """
UPDATE games SET status = 'done', moves = %s, trace = %s, error_counts = %s, engine_version = %s,
       engine_nodes = %s, grading_version = %s, analysis_seconds = %s, error = NULL
 WHERE id = %s
"""


async def analyse_game(game_id: str) -> None:
    async with get_pool().connection() as conn:
        game = await (
            await conn.execute("SELECT status, pgn FROM games WHERE id = %s", (game_id,))
        ).fetchone()
        if game is None:
            return
        if game["status"] != "done":
            await conn.execute(
                "UPDATE games SET status = 'running', trace = '[]', error = NULL WHERE id = %s",
                (game_id,),
            )

    with bind(game_id=game_id):
        if game["status"] != "done":
            await _analyse(game_id, game["pgn"])
    await check_reports_of_game(game_id)


async def _analyse(game_id: str, pgn: str) -> None:
    parsed = parse_pgn(pgn)
    engine = get_engine()
    trace: list[int] = []

    async def save_trace(_: int, position: Position) -> None:
        best = position.lines[0] if position.lines else None
        trace.append(capped_cp(best.cp, best.mate) if best else 0)
        if len(trace) % TRACE_EVERY == 0:
            async with get_pool().connection() as conn:
                await conn.execute(
                    "UPDATE games SET trace = %s WHERE id = %s", (Jsonb(trace), game_id)
                )

    started = time.perf_counter()
    positions = await engine.evaluate_game(parsed.start_fen, parsed.moves_uci, save_trace)
    evals = [PositionEval.model_validate(p, from_attributes=True) for p in positions]
    result = grade_game(parsed.start_fen, parsed.moves_uci, evals)
    seconds = round(time.perf_counter() - started, 2)
    moves = [m.model_dump(mode="json") for m in result.moves]
    async with get_pool().connection() as conn:
        await conn.execute(
            _SAVE,
            (
                Jsonb(moves),
                Jsonb(result.trace),
                Jsonb(result.error_counts),
                engine.version,
                engine.nodes,
                GRADING_VERSION,
                seconds,
                game_id,
            ),
        )
    log.info("game analysed", extra={"plies": len(parsed.moves_uci), "seconds": seconds})


async def give_up_on_game(game_id: str, reason: str) -> None:
    """The game's last try failed (or it can never work): skip it, and let its reports carry on."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE games SET status = 'failed', error = %s WHERE id = %s AND status <> 'done'",
            (reason[:500], game_id),
        )
    log.warning("game skipped after failing", extra={"game_id": game_id, "reason": reason[:200]})
    await check_reports_of_game(game_id)

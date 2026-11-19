"""The repeating checks' logic: stuck reports and housekeeping (docs/BACKEND.md section 6).

A report is stuck when it's queued or running but no job anywhere can move it forward: its prepare
step, an unfinished game, or its build. That can only come from a bug, so each repair logs a
WARNING. The repair re-queues exactly the missing work; if that work then fails for good, the
normal last-try handling marks the game or report failed. Waiting in a long line is never "stuck".
"""

import logging

from app.db import get_pool
from app.reports.queueing import queue_build, queue_game, queue_prepare

log = logging.getLogger(__name__)

QUIET_FOR = "2 minutes"  # skip reports changed recently: they may be between two steps

_CANDIDATES = f"""
SELECT r.id, r.status FROM reports r
 WHERE r.status IN ('queued', 'running') AND r.updated_at < now() - interval '{QUIET_FOR}'
   AND NOT EXISTS (
     SELECT 1 FROM procrastinate_jobs j
      WHERE j.status IN ('todo', 'doing')
        AND ((j.task_name IN ('prepare_report', 'build_report') AND j.args ->> 'report_id' = r.id)
             OR (j.task_name = 'analyse_game' AND j.args ->> 'game_id' IN (
                   SELECT g.id FROM report_games rg JOIN games g ON g.id = rg.game_id
                    WHERE rg.report_id = r.id AND g.status NOT IN ('done', 'failed')))))
"""


async def repair_stuck_reports() -> int:
    """Re-queue the missing work of every report nothing can finish. Returns how many."""
    async with get_pool().connection() as conn:
        stuck = await (await conn.execute(_CANDIDATES)).fetchall()
    for report in stuck:
        report_id = report["id"]
        async with get_pool().connection() as conn:
            games = await (
                await conn.execute(
                    "SELECT g.id, g.status FROM report_games rg JOIN games g ON g.id = rg.game_id"
                    " WHERE rg.report_id = %s",
                    (report_id,),
                )
            ).fetchall()
        unfinished = [g["id"] for g in games if g["status"] not in ("done", "failed")]
        if report["status"] == "queued" or not games:
            action = "prepare"
            await queue_prepare(report_id)
        elif unfinished:
            action = "games"
            for game_id in unfinished:
                await queue_game(game_id)
        else:
            action = "build"
            await queue_build(report_id)
        log.warning(
            "stuck report repaired (this means a bug)",
            extra={"report_id": report_id, "requeued": action},
        )
    return len(stuck)


async def delete_expired_cache() -> None:
    async with get_pool().connection() as conn:
        await conn.execute("DELETE FROM cache WHERE expires_at < now() - interval '1 day'")

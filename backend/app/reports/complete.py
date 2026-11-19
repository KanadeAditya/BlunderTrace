"""The last-game check, and failing a report.

When a game finishes (or gives up), each report still running that includes it asks: "was that my
last unfinished game?" The trap: two workers finishing the last two games at the same instant each
see the other's game unfinished, and nobody queues the build. The fix: lock the report's row first
(`SELECT ... FOR UPDATE`), so the two checks take turns. Only reports still running are checked, so
a finished report is never rebuilt (fix 2 of the second check).
"""

import logging

from psycopg.types.json import Jsonb

from app.db import get_pool
from app.reports.queueing import queue_build

log = logging.getLogger(__name__)

_COUNT = """
SELECT count(*) AS total,
       count(*) FILTER (WHERE g.status IN ('done', 'failed')) AS finished
  FROM report_games rg JOIN games g ON g.id = rg.game_id
 WHERE rg.report_id = %s
"""


async def check_report_complete(report_id: str) -> bool:
    """Queue the build if every game of this running report is finished. True if it did."""
    async with get_pool().connection() as conn, conn.transaction():
        row = await (
            await conn.execute("SELECT status FROM reports WHERE id = %s FOR UPDATE", (report_id,))
        ).fetchone()
        if row is None or row["status"] != "running":
            return False
        counts = await (await conn.execute(_COUNT, (report_id,))).fetchone()
        if counts["total"] == 0 or counts["finished"] < counts["total"]:
            return False
    await queue_build(report_id)  # its locks mean it can only be queued once
    return True


async def check_reports_of_game(game_id: str) -> None:
    async with get_pool().connection() as conn:
        rows = await (
            await conn.execute(
                "SELECT rg.report_id FROM report_games rg JOIN reports r ON r.id = rg.report_id"
                " WHERE rg.game_id = %s AND r.status = 'running'",
                (game_id,),
            )
        ).fetchall()
    for row in rows:
        await check_report_complete(row["report_id"])


async def fail_report(report_id: str, code: str, detail: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE reports SET status = 'failed', error = %s, detail = %s, finished_at = now()"
            " WHERE id = %s AND status IN ('queued', 'running')",
            (code, detail, report_id),
        )
    log.warning("report failed", extra={"report_id": report_id, "error": code})


async def add_notes(report_id: str, notes: list[str]) -> None:
    async with get_pool().connection() as conn:
        await conn.execute("UPDATE reports SET notes = %s WHERE id = %s", (Jsonb(notes), report_id))

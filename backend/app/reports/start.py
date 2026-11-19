"""Starting a report (`POST /api/reports`), in the order of docs/BACKEND.md section 9:

check the player -> any games in that time control? -> identical report running? join it ->
identical report finished in the last 10 minutes? reuse it -> too busy? -> create it and queue it.
"""

import logging
import secrets
import string

from app.config import get_settings
from app.db import get_pool
from app.reports.errors import Busy, NoGames
from app.reports.players import lookup_player
from app.reports.queueing import queue_prepare

log = logging.getLogger(__name__)

_ID_LETTERS = string.ascii_lowercase + string.digits


def new_id(prefix: str) -> str:
    """ "r_" or "g_" + 10 random letters/digits: unguessable, so a report link is its own key."""
    return prefix + "".join(secrets.choice(_ID_LETTERS) for _ in range(10))


_FIND = """
SELECT id, status FROM reports
 WHERE username = %s AND time_control = %s AND games_requested = %s
   AND (status IN ('queued', 'running')
        OR (status = 'done' AND finished_at > now() - make_interval(mins => %s)))
 ORDER BY status = 'done', finished_at DESC NULLS FIRST
 LIMIT 1
"""
_CREATE = """
INSERT INTO reports (id, username, time_control, games_requested) VALUES (%s, %s, %s, %s)
ON CONFLICT (username, time_control, games_requested) WHERE status IN ('queued', 'running')
DO NOTHING
RETURNING id
"""


async def start_report(username: str, time_control: str, games: int) -> tuple[str, str]:
    """Returns (report id, status): "queued" for a new report, "running" when joining one, and
    "done" when reusing one that finished in the last REPORT_REUSE_MINUTES."""
    username = username.lower()
    player = await lookup_player(username)  # unknown player -> PlayerNotFound (404)
    classes = ("rapid", "blitz") if time_control == "both" else (time_control,)
    if sum(player.games[c] for c in classes) == 0:
        raise NoGames(username, time_control)

    settings = get_settings()
    key = (username, time_control, games)
    async with get_pool().connection() as conn:
        found = await (await conn.execute(_FIND, (*key, settings.report_reuse_minutes))).fetchone()
        if found:
            return found["id"], found["status"]
        active = await (
            await conn.execute(
                "SELECT count(*) AS n FROM reports WHERE status IN ('queued', 'running')"
            )
        ).fetchone()
        if active["n"] >= settings.max_active_reports:
            log.warning(
                "capacity: busy limit reached, a new report was refused",
                extra={"active_reports": active["n"], "limit": settings.max_active_reports},
            )
            raise Busy()
        report_id = new_id("r_")
        created = await (await conn.execute(_CREATE, (report_id, *key))).fetchone()
        if created is None:
            # An identical request won the race a moment ago (the partial unique index): join it.
            found = await (
                await conn.execute(_FIND, (*key, settings.report_reuse_minutes))
            ).fetchone()
            return found["id"], found["status"]
    await queue_prepare(report_id)
    log.info("report started", extra={"report_id": report_id, "time_control": time_control})
    return report_id, "queued"

"""Putting jobs in the queue, by task name (the task functions live in app.jobs).

Every job gets a lock name used twice (gap 6 of the final check):
- as a queueing lock: never two *waiting* jobs with the same name ("already queued" is fine);
- as a running lock: never two *running* at once; a second one waits its turn.
So a game wanted by two reports at the same moment is analysed once.
"""

from procrastinate.exceptions import AlreadyEnqueued

from app.db.queue import PRIORITY_GAME, PRIORITY_REPORT, queue_app


async def _queue(task: str, priority: int, lock: str, **arguments: str) -> None:
    deferrer = queue_app.configure_task(task, priority=priority, lock=lock, queueing_lock=lock)
    try:
        await deferrer.defer_async(**arguments)
    except AlreadyEnqueued:
        pass  # an identical job is already waiting: nothing more to do


async def queue_prepare(report_id: str) -> None:
    await _queue("prepare_report", PRIORITY_REPORT, f"report:{report_id}", report_id=report_id)


async def queue_game(game_id: str) -> None:
    await _queue("analyse_game", PRIORITY_GAME, f"game:{game_id}", game_id=game_id)


async def queue_build(report_id: str) -> None:
    await _queue("build_report", PRIORITY_REPORT, f"report-build:{report_id}", report_id=report_id)

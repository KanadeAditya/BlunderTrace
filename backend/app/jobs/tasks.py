"""The background tasks the workers run (Procrastinate). Each is thin: it calls into app.reports.

Retries (gap 5 of the final check): only **temporary** errors are retried; anything else would fail
the same way again, so it fails at once. When a task gives up (a permanent error, or its last try),
it marks what it was working on as failed, so no report is left "Analysing" forever:
- prepare: the report fails (chesscom_unavailable or analysis_failed);
- analyse: the game is skipped and its reports carry on without it;
- build: the report fails (analysis_failed).
"""

import logging

import psycopg
from procrastinate import JobContext
from procrastinate.jobs import Job
from procrastinate.retry import BaseRetryStrategy, RetryDecision

from app import reports
from app.chesscom import ChesscomUnavailable
from app.db.queue import PRIORITY_CHECKS, PRIORITY_GAME, PRIORITY_REPORT, queue_app
from app.engine import EngineCrashed
from app.logs import bind

log = logging.getLogger(__name__)


class TemporaryErrors(BaseRetryStrategy):
    """Retry only the listed exception types, waiting the given seconds before each retry."""

    def __init__(self, waits: tuple[int, ...], retry_on: tuple[type[BaseException], ...]) -> None:
        self.waits, self.retry_on = waits, retry_on

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if not isinstance(exception, self.retry_on) or job.attempts >= len(self.waits):
            return None
        return RetryDecision(retry_in={"seconds": self.waits[job.attempts]})


DB_HICCUP = (psycopg.OperationalError,)  # a dropped connection, a restart of Postgres
PREPARE_RETRY = TemporaryErrors((5, 30), (ChesscomUnavailable, *DB_HICCUP))  # backoff
GAME_RETRY = TemporaryErrors((3, 10), (EngineCrashed, *DB_HICCUP))
BUILD_RETRY = TemporaryErrors((3, 10), DB_HICCUP)


def gives_up(strategy: TemporaryErrors, error: Exception, context: JobContext) -> bool:
    return strategy.get_retry_decision(exception=error, job=context.job) is None


@queue_app.task(
    name="prepare_report", retry=PREPARE_RETRY, pass_context=True, priority=PRIORITY_REPORT
)
async def prepare_report(context: JobContext, report_id: str) -> None:
    with bind(report_id=report_id, job="prepare_report"):
        try:
            await reports.prepare_report(report_id)
        except Exception as error:
            if gives_up(PREPARE_RETRY, error, context):
                if isinstance(error, ChesscomUnavailable):
                    code = "chesscom_unavailable"
                    detail = (
                        "chess.com isn't responding right now. Please try again in a few minutes."
                    )
                else:
                    code, detail = "analysis_failed", "Something went wrong. Please try again."
                await reports.fail_report(report_id, code, detail)
            raise


@queue_app.task(name="analyse_game", retry=GAME_RETRY, pass_context=True, priority=PRIORITY_GAME)
async def analyse_game(context: JobContext, game_id: str) -> None:
    with bind(game_id=game_id, job="analyse_game"):
        try:
            await reports.analyse_game(game_id)
        except Exception as error:
            if gives_up(GAME_RETRY, error, context):
                await reports.give_up_on_game(game_id, f"{type(error).__name__}: {error}")
            raise


@queue_app.task(name="build_report", retry=BUILD_RETRY, pass_context=True, priority=PRIORITY_REPORT)
async def build_report(context: JobContext, report_id: str) -> None:
    with bind(report_id=report_id, job="build_report"):
        try:
            await reports.build_report(report_id)
        except Exception as error:
            if gives_up(BUILD_RETRY, error, context):
                await reports.fail_report(
                    report_id, "analysis_failed", "Something went wrong. Please try again."
                )
            raise


# --- repeating tasks (run by the workers themselves; each run happens once) --------------------


@queue_app.periodic(cron="* * * * *")
@queue_app.task(
    name="retry_stalled_jobs", queueing_lock="retry_stalled_jobs", priority=PRIORITY_CHECKS
)
async def retry_stalled_jobs(timestamp: int) -> None:
    """Jobs whose worker stopped sending heartbeats (a crash, a restart) go back in the queue."""
    for job in await queue_app.job_manager.get_stalled_jobs(seconds_since_heartbeat=60):
        log.warning(
            "job's worker stopped responding; retrying it",
            extra={"job_id": job.id, "task": job.task_name},
        )
        await queue_app.job_manager.retry_job(job)


@queue_app.periodic(cron="*/5 * * * *")
@queue_app.task(
    name="repair_stuck_reports", queueing_lock="repair_stuck_reports", priority=PRIORITY_CHECKS
)
async def repair_stuck_reports(timestamp: int) -> None:
    await reports.repair_stuck_reports()


@queue_app.periodic(cron="17 3 * * *")
@queue_app.task(name="housekeeping", queueing_lock="housekeeping", priority=PRIORITY_CHECKS)
async def housekeeping(timestamp: int) -> None:
    """Daily: finished jobs older than 30 days and long-expired cache rows are deleted."""
    await queue_app.job_manager.delete_old_jobs(nb_hours=30 * 24, include_failed=True)
    await reports.delete_expired_cache()

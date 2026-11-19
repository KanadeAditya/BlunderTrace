"""The product's steps: start a report, prepare it, analyse a game, build the report, read results.

The only folder that coordinates the others: it calls chess.com, the engine, the analysis and RAG,
and stores results through the database. The HTTP routes and the background jobs both call in here.
"""

from app.reports.analyse import analyse_game, give_up_on_game
from app.reports.build import build_report
from app.reports.complete import check_report_complete, fail_report
from app.reports.errors import TIME_LABELS, Busy, GameNotFound, NoGames, ReportNotFound
from app.reports.maintenance import delete_expired_cache, repair_stuck_reports
from app.reports.players import PlayerSummary, lookup_player
from app.reports.prepare import prepare_report
from app.reports.queueing import queue_build, queue_game, queue_prepare
from app.reports.read import get_game, get_report
from app.reports.start import start_report

__all__ = [
    "TIME_LABELS",
    "Busy",
    "GameNotFound",
    "NoGames",
    "PlayerSummary",
    "ReportNotFound",
    "analyse_game",
    "build_report",
    "check_report_complete",
    "delete_expired_cache",
    "fail_report",
    "get_game",
    "get_report",
    "give_up_on_game",
    "lookup_player",
    "prepare_report",
    "queue_build",
    "queue_game",
    "queue_prepare",
    "repair_stuck_reports",
    "start_report",
]

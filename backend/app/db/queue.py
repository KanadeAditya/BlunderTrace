"""The job queue: one Procrastinate app object, shared by everything that queues or runs jobs.

It lives here, below the features, so `app.reports` can queue a job **by name** ("analyse_game")
without importing `app.jobs`, where the task functions are defined. The worker imports `app.jobs`,
which registers those functions on this same object.

Priorities (higher runs first): the repeating checks, then preparing and building reports, then
games, oldest first. So a report whose games are done is built within seconds, even while someone
else's games are waiting (gap 4 of the final check).
"""

from procrastinate import App, PsycopgConnector

from app.config import get_settings

PRIORITY_CHECKS = 20
PRIORITY_REPORT = 10
PRIORITY_GAME = 0

queue_app = App(connector=PsycopgConnector(conninfo=get_settings().database_url))

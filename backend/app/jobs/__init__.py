"""Background tasks run by the workers (Procrastinate). Thin: each task calls into app.reports.

Importing this package registers the tasks on the shared queue app (app.db.queue).
"""

from app.jobs import tasks

__all__ = ["tasks"]

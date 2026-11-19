"""Expected failures of the report flow. The API turns each into its HTTP status and error code."""

TIME_LABELS = {"rapid": "rapid", "blitz": "blitz", "both": "rapid or blitz"}


class NoGames(Exception):
    """The player has never played this time control (422 no_games)."""

    def __init__(self, username: str, time_control: str) -> None:
        super().__init__(f"no {time_control} games for {username}")
        self.username = username
        self.time_control = time_control


class Busy(Exception):
    """Too many reports are queued or running (503 busy)."""


class ReportNotFound(Exception):
    pass


class GameNotFound(Exception):
    pass

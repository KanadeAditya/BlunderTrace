"""Winning chances: turning an engine score into "how likely is this side to win", 0 to 100.

Lichess's formula (scalachess eval.scala, MIT). A pawn up in a level game is a big swing; a pawn
up when already a rook up barely matters. Grading by lost winning chances therefore flags only
moves that changed the game.
"""

import math

CP_CAP = 1000  # scores are capped at ±10 pawns; a forced mate counts as the cap


def capped_cp(cp: int | None, mate: int | None) -> int:
    """One number for any score (White's point of view): centipawns, capped, mate as the cap."""
    if mate is not None:
        return CP_CAP if mate > 0 else -CP_CAP
    return max(-CP_CAP, min(CP_CAP, cp or 0))


def win_percent(cp: int) -> float:
    """Winning chances in % for the side the score is for."""
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)

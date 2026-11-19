"""Error grades: blunder, mistake, inaccuracy (Lichess's rules, lila Advice.scala).

Scores here are from the **mover's** point of view (positive = good for the side that moved).

- Both scores in centipawns: grade by lost winning chances, 15 / 10 / 5 points.
- A forced mate appears or disappears: Lichess's mate rules. Allowing a forced mate is a blunder
  unless the mover was already lost (> 7 pawns down: mistake, > 10: inaccuracy); throwing away your
  own forced mate is a blunder unless you're still far ahead (> 7 pawns: mistake, > 10: inaccuracy).
"""

from typing import Literal

import chess

from app.analysis.winning import win_percent

ErrorGrade = Literal["inaccuracy", "mistake", "blunder"]

BLUNDER, MISTAKE, INACCURACY = 15.0, 10.0, 5.0  # winning chances lost, in points
GREAT_GAP = 10.0  # "great": the second-best move is at least this much worse
EXCELLENT_BELOW, GOOD_BELOW = 2.0, 5.0
# "Great" and "brilliant" only when the mover wasn't already winning by a mile...
BRILLIANT_BELOW = 90.0
# ...and a brilliant sacrifice must leave the mover at least level.
BRILLIANT_KEEPS = 50.0
GRADING_VERSION = 2  # bump when any rule here changes; stored with each analysed game


def error_grade(
    cp_before: int | None, mate_before: int | None, cp_after: int | None, mate_after: int | None
) -> ErrorGrade | None:
    """The error grade of a move, or None. All values from the mover's point of view."""
    if mate_before is None and mate_after is None:
        loss = win_percent(cp_before or 0) - win_percent(cp_after or 0)
        if loss >= BLUNDER:
            return "blunder"
        if loss >= MISTAKE:
            return "mistake"
        if loss >= INACCURACY:
            return "inaccuracy"
        return None

    mate_created = mate_before is None and mate_after is not None and mate_after < 0
    mate_lost = (
        mate_before is not None and mate_before > 0 and (mate_after is None or mate_after < 0)
    )
    if mate_created:
        before = cp_before or 0
        return "inaccuracy" if before < -999 else "mistake" if before < -700 else "blunder"
    if mate_lost:
        after = cp_after or 0  # no centipawn score when the opponent now has a mate: 0, a blunder
        return "inaccuracy" if after > 999 else "mistake" if after > 700 else "blunder"
    return None  # e.g. a mate that just got a move longer: not an error


def quality_grade(loss: float) -> Literal["excellent", "good"] | None:
    """For a non-best move that isn't an error."""
    if loss < EXCELLENT_BELOW:
        return "excellent"
    if loss < GOOD_BELOW:
        return "good"
    return None


def is_obvious(before: chess.Board, move: chess.Move, previous: chess.Move | None) -> bool:
    """A best move nobody would call "great": checked on real club games, these made up most of
    the raw "only good move" cases.

    - getting out of check;
    - recapturing on the square the opponent just captured on;
    - taking a piece that nothing defends.
    """
    if before.is_check():
        return True
    if not before.is_capture(move):
        return False
    if previous is not None and previous.to_square == move.to_square:
        return True  # a recapture (the previous move landed there, usually by capturing)
    return not before.is_attacked_by(not before.turn, move.to_square)  # the piece was undefended

"""Naming tactics with Lichess's own puzzle tagger (vendored in app/vendor/lichess_puzzler).

The tagger understands puzzles: a starting position, a "blunder" move, then the solution, which is
played by the other side (the solver). We turn our moments into exactly that shape:

- **What a move allowed:** start before the move; the move is the blunder; the opponent's best
  reply line (from Stockfish) is the solution.
- **What a move missed:** start before the opponent's previous move; that move is the "blunder";
  the mover's best line is the solution.
- **A sacrifice (for "brilliant"):** like a miss, but the solution is the move actually played,
  followed by the engine's line.

The bar: a tactic only counts if its line wins at least 2 pawns of material and keeps it, or mates,
within 10 half-moves, as with Lichess puzzles. The line is cut where the gain is made, so the tagger
doesn't read meaning into moves far down the engine's line.
"""

import logging

import chess
import chess.pgn

from app.analysis.models import THEMES
from app.vendor.lichess_puzzler import cook
from app.vendor.lichess_puzzler.model import Puzzle

log = logging.getLogger(__name__)

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
MIN_GAIN = 2  # pawns
MAX_PLIES = 10


def material(board: chess.Board, color: chess.Color) -> int:
    """`color`'s material minus the opponent's, in pawns."""
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        total += value * (
            len(board.pieces(piece_type, color)) - len(board.pieces(piece_type, not color))
        )
    return total


def winning_line(board: chess.Board, line: list[chess.Move]) -> list[chess.Move] | None:
    """The start of `line` that mates, or wins ≥ 2 pawns and keeps them, for the side to move.

    None when the line does neither within MAX_PLIES: then no tactic is named.
    """
    solver = board.turn
    start = material(board, solver)
    played = board.copy()
    line = line[:MAX_PLIES]
    for i, move in enumerate(line):
        if move not in played.legal_moves:
            return None
        played.push(move)
        if played.is_checkmate():
            return line[: i + 1]
        if i % 2 == 0 and material(played, solver) - start >= MIN_GAIN:
            # The gain must survive the opponent's next move in the line (no recapture undoes it).
            if i + 1 >= len(line):
                return line[: i + 1]
            reply = played.copy()
            reply.push(line[i + 1])
            if material(reply, solver) - start >= MIN_GAIN:
                return line[: i + 1]
    return None


def _puzzle(start: chess.Board, first: chess.Move, solution: list[chess.Move]) -> Puzzle:
    # From the bare position: Game.from_board() would replay the board's whole move history.
    game = chess.pgn.Game.from_board(chess.Board(start.fen()))
    node = game.add_main_variation(first)
    for move in solution:
        node = node.add_main_variation(move)
    return Puzzle("blundertrace", game, 400)  # the score only matters for tags we don't use


def _cook(start: chess.Board, first: chess.Move, solution: list[chess.Move]) -> list[str]:
    try:
        tags = cook.cook(_puzzle(start, first, solution))
    except Exception:  # third-party code on unusual positions: a missing tag, never a crash
        log.warning("tagger failed on a position", exc_info=True, extra={"fen": start.fen()})
        return []
    return [theme for theme in THEMES if theme in tags]


def allowed_themes(before: chess.Board, move: chess.Move, reply_line: list[str]) -> list[str]:
    """Tactics the opponent can play because of `move` (from the position `before` it)."""
    after = before.copy()
    after.push(move)
    solution = winning_line(after, [chess.Move.from_uci(m) for m in reply_line])
    return _cook(before, move, solution) if solution else []


def gives_material(before: chess.Board, move: chess.Move, reply_line: list[str]) -> bool:
    """Does the opponent's best line after `move` win ≥ 2 pawns or mate, named tactic or not?"""
    after = before.copy()
    after.push(move)
    return winning_line(after, [chess.Move.from_uci(m) for m in reply_line]) is not None


def missed_themes(
    before_previous: chess.Board, previous: chess.Move, best_line: list[str]
) -> list[str]:
    """Winning tactics the mover had (their best line), from before the opponent's last move."""
    position = before_previous.copy()
    position.push(previous)
    solution = winning_line(position, [chess.Move.from_uci(m) for m in best_line])
    return _cook(before_previous, previous, solution) if solution else []


def offers_material(before: chess.Board, move: chess.Move, reply_line: list[str]) -> bool:
    """After `move`, does the opponent's best reply take material, leaving the mover ≥ 2 pawns
    down compared with before the move? That's what makes a move a sacrifice at all."""
    if not reply_line:
        return False
    after = before.copy()
    after.push(move)
    reply = chess.Move.from_uci(reply_line[0])
    if reply not in after.legal_moves or not after.is_capture(reply):
        return False
    after.push(reply)
    return material(before, before.turn) - material(after, before.turn) >= MIN_GAIN


def is_sacrifice(
    before_previous: chess.Board, previous: chess.Move, move: chess.Move, line_after: list[str]
) -> bool:
    """Did the mover give up material with `move` (then win it back, per the engine's line)?"""
    # A short line: deep in an engine line, ordinary exchanges look like sacrifices.
    solution = [move] + [chess.Move.from_uci(m) for m in line_after[:4]]
    try:
        return bool(cook.sacrifice(_puzzle(before_previous, previous, solution)))
    except Exception:
        log.warning("sacrifice check failed", exc_info=True)
        return False

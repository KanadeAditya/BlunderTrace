"""The two lines shown for an error, the facts behind their notes, and the threat arrows.

- Better line: Stockfish's best line from the position before the move.
- Punishing (refutation) line: Stockfish's best line after the move, starting with the opponent's
  reply.
Both are shown as 3 to 5 half-moves. The note facts are stored with the move; notes.py turns them
into a sentence for whoever is reading (gap 1 of the final check).
"""

import chess

from app.analysis.models import BetterFacts, Color, RefutationFacts
from app.analysis.tagging import PIECE_VALUES, material
from app.analysis.winning import CP_CAP

SHOWN_PLIES = 5
PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}
_VALUE_WITH_KING = {**PIECE_VALUES, chess.KING: 100}


def san_line(board: chess.Board, uci_moves: list[str], plies: int = SHOWN_PLIES) -> list[str]:
    """Up to `plies` moves of a UCI line, in SAN (stops at the first illegal move)."""
    played = board.copy()
    sans: list[str] = []
    for uci in uci_moves[:plies]:
        move = chess.Move.from_uci(uci)
        if move not in played.legal_moves:
            break
        sans.append(played.san(move))
        played.push(move)
    return sans


def move_label(board: chess.Board, san: str) -> str:
    """ "18. Be2" for White, "18… Be2" for Black (the move number of the position `board`)."""
    dots = "." if board.turn == chess.WHITE else "…"
    return f"{board.fullmove_number}{dots} {san}"


def format_eval(cp: int | None, mate: int | None) -> str:
    """White's point of view, the way chess players write it: "+1.2", "−0.4", "#3", "#−2"."""
    if mate is not None:
        return f"#{mate}" if mate > 0 else f"#−{-mate}"
    pawns = max(-CP_CAP, min(CP_CAP, cp or 0)) / 100
    return f"+{pawns:.1f}" if pawns >= 0 else f"−{-pawns:.1f}"


def _attacked_targets(board: chess.Board, square: chess.Square) -> list[tuple[str, str]]:
    """The other side's pieces (knight or better, or the king) attacked by the piece on `square`."""
    attacker = board.piece_at(square)
    if attacker is None:
        return []
    found = []
    for target in board.attacks(square):
        piece = board.piece_at(target)
        if piece and piece.color != attacker.color and piece.piece_type != chess.PAWN:
            found.append((piece.piece_type, target))
    found.sort(key=lambda t: _VALUE_WITH_KING[t[0]], reverse=True)
    return [(PIECE_NAMES[p], chess.square_name(s)) for p, s in found]


def refutation_facts(
    before: chess.Board,
    move: chess.Move,
    reply_line: list[str],
    theme: str | None,
    win_before: float,
    win_after: float,
) -> tuple[RefutationFacts, list[tuple[str, str]] | None]:
    """The facts for "Show why it's bad", plus the threat arrows. First matching rule wins."""
    mover = before.turn
    after = before.copy()
    after.push(move)
    shown = [chess.Move.from_uci(m) for m in reply_line[:SHOWN_PLIES]]
    common = {"theme": theme, "before": round(win_before), "after": round(win_after)}
    # (targets are added below, once known: every rule keeps them for the report examples)

    played, lost = after.copy(), []
    for reply in shown:
        if reply not in played.legal_moves:
            break
        captured = played.piece_at(reply.to_square)
        if captured is not None and captured.color == mover:
            lost.append(captured.piece_type)
        played.push(reply)

    arrows = None
    targets: list[tuple[str, str]] = []
    if shown and shown[0] in after.legal_moves:
        taken = after.piece_at(shown[0].to_square)
        if taken is not None and taken.color == mover:
            common["reply_takes"] = PIECE_NAMES[taken.piece_type]
        first = after.copy()
        first.push(shown[0])
        targets = _attacked_targets(first, shown[0].to_square)
        sq = chess.square_name(shown[0].to_square)
        arrows = [(sq, target_sq) for _, target_sq in targets] or None

    common["targets"] = targets[:2]
    if played.is_checkmate():
        return RefutationFacts(rule="mate", **common), arrows
    if material(after, mover) - material(played, mover) >= 2 and lost:
        piece = PIECE_NAMES[max(lost, key=lambda p: PIECE_VALUES.get(p, 0))]
        return RefutationFacts(rule="material", piece=piece, **common), arrows
    if len(targets) >= 2:
        reply_san = after.san(shown[0])
        facts = RefutationFacts(rule="double_attack", reply=reply_san, **common)
        return facts, arrows
    return RefutationFacts(rule="drop", **common), arrows


def better_facts(
    before: chess.Board, best_line: list[str], cp: int | None, mate: int | None, mover_win: float
) -> BetterFacts | None:
    """The facts for "Show better move". `cp`/`mate`: the best line's score, White's view."""
    sans = san_line(before, best_line, plies=1)
    if not sans:
        return None
    rule = "advantage" if mover_win >= 60 else "level" if mover_win >= 40 else "damage"
    return BetterFacts(rule=rule, move=move_label(before, sans[0]), eval=format_eval(cp, mate))


def color_name(color: chess.Color) -> Color:
    return "white" if color == chess.WHITE else "black"

"""
describe(board): deterministic, rule-based translation of a chess position into plain English.

No AI. The same board always produces the same text. It is run on both corpus positions and
user positions so they land in the same embedding space. Answers a fixed list of questions:
phase, material, opening, pawn structure, open files, king safety, (optional) mistake type.
"""
from __future__ import annotations

import chess

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
COLOR_NAMES = {chess.WHITE: "White", chess.BLACK: "Black"}
FILES = "abcdefgh"
ENDGAME_MAX_PIECES = 6          # knights+bishops+rooks+queens on board (same rule as Lichess)
OPENING_MIN_PIECES = 12         # 14 at the start; at most one minor-piece trade per side
OPENING_MAX_MOVE = 12


# ---------- individual facts ----------

def piece_count(board: chess.Board) -> int:
    """Knights, bishops, rooks and queens of both sides (no pawns, no kings)."""
    return sum(1 for p in board.piece_map().values() if p.piece_type not in (chess.PAWN, chess.KING))


def game_phase(board: chess.Board) -> str:
    pieces = piece_count(board)
    if pieces <= ENDGAME_MAX_PIECES:
        return "Endgame"
    if board.fullmove_number <= OPENING_MAX_MOVE and pieces >= OPENING_MIN_PIECES:
        return "Opening"
    return "Middlegame"


def material_balance(board: chess.Board) -> str:
    """Point balance only. A piece-by-piece list misleads mid-exchange (e.g. right after a capture)."""
    totals = {c: sum(PIECE_VALUES[pt] * len(board.pieces(pt, c)) for pt in PIECE_VALUES)
              for c in chess.COLORS}
    diff = totals[chess.WHITE] - totals[chess.BLACK]
    if diff == 0:
        return "Material is equal."
    leader = chess.WHITE if diff > 0 else chess.BLACK
    points = abs(diff)
    return f"{COLOR_NAMES[leader]} is ahead by {points} point{'s' if points != 1 else ''} of material."


def _pawn_files(board: chess.Board, color: chess.Color) -> dict[int, list[int]]:
    files: dict[int, list[int]] = {}
    for sq in board.pieces(chess.PAWN, color):
        files.setdefault(chess.square_file(sq), []).append(chess.square_rank(sq))
    return files


def _is_passed(board: chess.Board, sq: chess.Square, color: chess.Color) -> bool:
    f, r = chess.square_file(sq), chess.square_rank(sq)
    for esq in board.pieces(chess.PAWN, not color):
        ef, er = chess.square_file(esq), chess.square_rank(esq)
        if abs(ef - f) <= 1 and (er > r if color == chess.WHITE else er < r):
            return False
    return True


def _is_backward(board: chess.Board, sq: chess.Square, color: chess.Color,
                 own_files: dict[int, list[int]]) -> bool:
    f, r = chess.square_file(sq), chess.square_rank(sq)
    neighbours = [rank for af in (f - 1, f + 1) for rank in own_files.get(af, [])]
    if not neighbours:
        return False                                     # that's isolated, not backward
    behind_or_level = (lambda nr: nr <= r) if color == chess.WHITE else (lambda nr: nr >= r)
    if any(behind_or_level(nr) for nr in neighbours):
        return False                                     # a neighbour can still support it
    stop = r + 1 if color == chess.WHITE else r - 1
    if not 0 <= stop <= 7:
        return False
    stop_sq = chess.square(f, stop)
    return any(board.piece_at(a) == chess.Piece(chess.PAWN, not color)
               for a in board.attackers(not color, stop_sq))


def pawn_structure(board: chess.Board) -> list[str]:
    sentences = []
    for color in chess.COLORS:
        own = _pawn_files(board, color)
        isolated, doubled, passed, backward = [], [], [], []
        for f, ranks in sorted(own.items()):
            letter = FILES[f]
            if len(ranks) > 1:
                doubled.append(f"doubled {letter}-pawns")
            if (f - 1) not in own and (f + 1) not in own:
                isolated.append(f"an isolated {letter}-pawn")
            for r in ranks:
                sq = chess.square(f, r)
                if _is_passed(board, sq, color):
                    passed.append(f"a passed {letter}-pawn")
                elif _is_backward(board, sq, color, own):
                    backward.append(f"a backward {letter}-pawn")
        features = isolated + doubled + backward + passed
        if features:
            sentences.append(f"{COLOR_NAMES[color]} has {_join(features)}.")
    return sentences


def open_files(board: chess.Board) -> list[str]:
    white, black = _pawn_files(board, chess.WHITE), _pawn_files(board, chess.BLACK)
    fully_open, half = [], {chess.WHITE: [], chess.BLACK: []}
    for f in range(8):
        w, b = f in white, f in black
        if not w and not b:
            fully_open.append(FILES[f])
        elif not w:
            half[chess.WHITE].append(FILES[f])
        elif not b:
            half[chess.BLACK].append(FILES[f])
    sentences = []
    if fully_open:
        verb = "is" if len(fully_open) == 1 else "are"
        sentences.append(f"The {_files_phrase(fully_open)} {verb} open.")
    for color in chess.COLORS:
        if half[color]:
            article = "a " if len(half[color]) == 1 else ""
            sentences.append(f"{COLOR_NAMES[color]} has {article}half-open {_files_phrase(half[color])}.")
    return sentences


def _files_phrase(letters: list[str]) -> str:
    """['c'] -> 'c-file'; ['a', 'c', 'd'] -> 'a-, c- and d-files'."""
    if len(letters) == 1:
        return f"{letters[0]}-file"
    return _join([x + "-" for x in letters[:-1]] + [letters[-1] + "-files"])


KINGSIDE_FILES, QUEENSIDE_FILES = (5, 6, 7), (0, 1, 2)     # f-g-h, a-b-c


def _shield_files_covered(board: chess.Board, color: chess.Color, files: tuple[int, ...]) -> int:
    """How many of `files` have a friendly pawn on the 2nd or 3rd rank in front of the king."""
    ranks = (1, 2) if color == chess.WHITE else (6, 5)
    pawn = chess.Piece(chess.PAWN, color)
    return sum(1 for f in files if any(board.piece_at(chess.square(f, r)) == pawn for r in ranks))


def king_safety(board: chess.Board, phase: str) -> list[str]:
    """In the endgame an active king is normal, so only check is reported."""
    sentences = []
    for color in chess.COLORS:
        name = COLOR_NAMES[color]
        ksq = board.king(color)
        if ksq is None:
            continue
        if phase != "Endgame":
            f, r = chess.square_file(ksq), chess.square_rank(ksq)
            home_rank = 0 if color == chess.WHITE else 7
            if r != home_rank:
                sentences.append(f"{name}'s king is exposed, away from its back rank.")
            elif f in KINGSIDE_FILES[1:] or f in QUEENSIDE_FILES:        # g/h or a/b/c: castled side
                side, files = (("kingside", KINGSIDE_FILES) if f >= 6
                               else ("queenside", QUEENSIDE_FILES))
                covered = _shield_files_covered(board, color, files)
                shield = ("an intact pawn shield" if covered == 3
                          else "a weakened pawn shield" if covered else "no pawn shield")
                sentences.append(f"{name}'s king is on the {side} with {shield}.")
            elif board.has_castling_rights(color):
                sentences.append(f"{name}'s king is in the centre and can still castle.")
            else:
                sentences.append(f"{name}'s king is stuck in the centre and can no longer castle.")
        if board.is_check() and board.turn == color:
            sentences.append(f"{name} is in check.")
    return sentences


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---------- public entry point ----------

def describe(board: chess.Board, opening: str | None = None,
             mistake: str | None = None, mistake_by: chess.Color | None = None,
             brief: bool = False) -> str:
    """Plain-English description of `board`.

    opening    -- opening name from the lookup table (not computed from the board).
    mistake    -- mistake type phrase from the engine-based detector, e.g. "allowed a fork".
    mistake_by -- which side made the mistake.
    brief      -- only mistake + phase + opening (no board details).

    The mistake comes first: it is the most important fact for retrieval and should not be
    drowned out by board details.
    """
    phase = game_phase(board)
    parts = []
    if mistake:
        who = f" by {COLOR_NAMES[mistake_by]}" if mistake_by is not None else ""
        parts.append(f"Mistake{who}: {mistake}.")
    parts.append(f"{phase}.")
    if opening:
        parts.append(f"{opening}.")
    if brief:
        return " ".join(parts)
    parts.append(material_balance(board))
    parts += pawn_structure(board)
    parts += open_files(board)
    parts += king_safety(board, phase)
    parts.append(f"{COLOR_NAMES[board.turn]} to move.")
    return " ".join(parts)

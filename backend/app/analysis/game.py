"""Analysing a whole game: engine results for every position in, one MoveRecord per half-move out.

Pure: no engine, no database. `evals[i]` is the engine's view of the position before half-move i+1
(so there are len(moves) + 1 of them, the last one for the final position).
"""

import chess

from app.analysis.grading import (
    BRILLIANT_BELOW,
    BRILLIANT_KEEPS,
    GREAT_GAP,
    error_grade,
    is_obvious,
    quality_grade,
)
from app.analysis.lines import better_facts, color_name, refutation_facts, san_line
from app.analysis.models import ERROR_GRADES, Eval, GameAnalysis, Grade, MoveRecord, PositionEval
from app.analysis.tagging import (
    allowed_themes,
    gives_material,
    is_sacrifice,
    missed_themes,
    offers_material,
)
from app.analysis.winning import CP_CAP, capped_cp, win_percent


def _terminal_cp(board: chess.Board) -> int:
    """White's score in a finished position: checkmate is the cap, any draw is 0."""
    if board.is_checkmate():
        return -CP_CAP if board.turn == chess.WHITE else CP_CAP
    return 0


def _white_score(board: chess.Board, position: PositionEval) -> tuple[int | None, int | None]:
    """(cp, mate) from White's point of view; a finished game gets its fixed score."""
    if position.lines:
        best = position.lines[0]
        return best.cp, best.mate
    return _terminal_cp(board), None


def _for(mover_white: bool, cp: int | None, mate: int | None) -> tuple[int | None, int | None]:
    """Flip a White-view score to the mover's view."""
    sign = 1 if mover_white else -1
    return (None if cp is None else sign * cp), (None if mate is None else sign * mate)


def analyse_game(start_fen: str, moves_uci: list[str], evals: list[PositionEval]) -> GameAnalysis:
    if len(evals) != len(moves_uci) + 1:
        raise ValueError("need one engine result per position (moves + 1)")
    boards = [chess.Board(start_fen)]
    for uci in moves_uci:
        board = boards[-1].copy()
        board.push(chess.Move.from_uci(uci))
        boards.append(board)

    records: list[MoveRecord] = []
    for i, uci in enumerate(moves_uci):
        before, after = boards[i], boards[i + 1]
        move = chess.Move.from_uci(uci)
        mover_white = before.turn == chess.WHITE
        here, there = evals[i], evals[i + 1]

        cp_b, mate_b = _for(mover_white, *_white_score(before, here))
        cp_a, mate_a = _for(mover_white, *_white_score(after, there))
        win_before = win_percent(capped_cp(cp_b, mate_b))
        win_after = win_percent(capped_cp(cp_a, mate_a))
        loss = max(0.0, win_before - win_after)

        best = here.lines[0] if here.lines else None
        best_uci = best.pv[0] if best and best.pv else None
        played_best = uci == best_uci
        second_gap = None
        if len(here.lines) >= 2:
            s_cp, s_mate = _for(mover_white, here.lines[1].cp, here.lines[1].mate)
            second_gap = win_before - win_percent(capped_cp(s_cp, s_mate))

        # The engine's own top move is never called an error (search depth can disagree slightly).
        grade: Grade | None = None if played_best else error_grade(cp_b, mate_b, cp_a, mate_a)
        reply_line = there.lines[0].pv if there.lines else []
        themes: list[str] = []
        missed: list[str] = []
        if grade is not None:
            themes = allowed_themes(before, move, reply_line) if reply_line else []
            if i >= 1 and best is not None:
                missed = missed_themes(
                    boards[i - 1], chess.Move.from_uci(moves_uci[i - 1]), best.pv
                )
            if missed and not themes and not gives_material(before, move, reply_line):
                grade = "miss"  # it let a winning tactic slip, without giving anything away itself
        elif played_best:
            previous = chess.Move.from_uci(moves_uci[i - 1]) if i >= 1 else None
            grade = "best"
            if (
                second_gap is not None
                and second_gap >= GREAT_GAP
                and win_before < BRILLIANT_BELOW
                and before.legal_moves.count() > 1
                and not is_obvious(before, move, previous)
            ):
                grade = "great"
            if (
                previous is not None
                and win_before < BRILLIANT_BELOW
                and win_after >= BRILLIANT_KEEPS
                and offers_material(before, move, reply_line)
                and is_sacrifice(boards[i - 1], previous, move, reply_line)
            ):
                grade = "brilliant"
        else:
            grade = quality_grade(loss) or "good"

        cp_white, mate_white = _white_score(after, there)
        record = MoveRecord(
            ply=i + 1,
            move_number=before.fullmove_number,
            color=color_name(before.turn),
            san=before.san(move),
            fen_after=after.fen(),
            eval=Eval(cp=cp_white, mate=mate_white),
            grade=grade,
            themes=themes,
            uci=uci,
            best_uci=best_uci,
            win_before=round(win_before, 2),
            win_after=round(win_after, 2),
            loss=round(loss, 2),
            second_gap=None if second_gap is None else round(second_gap, 2),
            missed_themes=missed,
        )
        if grade in ERROR_GRADES and best is not None:
            record.better_line = san_line(before, best.pv)
            record.refutation_line = san_line(after, reply_line) or None
            record.better_facts = better_facts(before, best.pv, best.cp, best.mate, win_before)
            theme = themes[0] if themes else None  # the tactic this move allowed, if any
            facts, arrows = refutation_facts(before, move, reply_line, theme, win_before, win_after)
            record.refutation_facts = facts
            record.refutation_arrows = arrows
        records.append(record)

    trace = [capped_cp(*_white_score(boards[i], evals[i])) for i in range(len(boards))]
    counts = {
        color: {g: 0 for g in ("blunder", "mistake", "inaccuracy", "miss")}
        for color in ("white", "black")
    }
    for r in records:
        if r.grade in counts[r.color]:
            counts[r.color][r.grade] += 1
    return GameAnalysis(moves=records, trace=trace, error_counts=counts)

"""Pure chess logic: win%, grades, the tagger adapter, lines, notes, openings. No engine needed."""

import chess
import pytest

from app.analysis import analyse_game, better_note, opening_family, parse_pgn, refutation_note
from app.analysis.grading import error_grade, quality_grade
from app.analysis.models import BetterFacts, EngineLine, PositionEval, RefutationFacts
from app.analysis.tagging import allowed_themes, missed_themes, winning_line
from app.analysis.winning import capped_cp, win_percent

# --- winning chances and grades --------------------------------------------------------------


def test_winning_chances_curve():
    assert win_percent(0) == pytest.approx(50)
    assert win_percent(1000) == pytest.approx(100 - win_percent(-1000))
    assert 97 < win_percent(1000) < 98
    assert (
        capped_cp(None, 3) == 1000
        and capped_cp(None, -1) == -1000
        and capped_cp(5000, None) == 1000
    )


@pytest.mark.parametrize(
    "before,after,grade",
    [
        (100, -300, "blunder"),  # 59% -> 25%: 34 points
        (0, -120, "mistake"),  # 50% -> 39.1%: 10.9 points
        (0, -110, "inaccuracy"),  # 50% -> 40.0%: 9.99 points, just short of a mistake
        (0, -40, None),  # under 5 points: not an error
        (900, 800, None),  # already winning big: 96.5% -> 95.0%, barely a change
    ],
)
def test_grades_from_lost_winning_chances(before, after, grade):
    assert error_grade(before, None, after, None) == grade


@pytest.mark.parametrize(
    "cp_before,mate_after,grade",
    [(100, -3, "blunder"), (-800, -3, "mistake"), (-1200, -3, "inaccuracy")],
)
def test_allowing_a_forced_mate(cp_before, mate_after, grade):
    assert error_grade(cp_before, None, None, mate_after) == grade


@pytest.mark.parametrize(
    "cp_after,mate_after,grade",
    [
        (0, None, "blunder"),
        (800, None, "mistake"),
        (1200, None, "inaccuracy"),
        (None, -2, "blunder"),
    ],
)
def test_throwing_away_your_own_forced_mate(cp_after, mate_after, grade):
    assert error_grade(None, 4, cp_after, mate_after) == grade


def test_a_mate_one_move_longer_is_not_an_error():
    assert error_grade(None, 2, None, 3) is None


def test_quality_grades():
    assert quality_grade(1.0) == "excellent"
    assert quality_grade(3.0) == "good"
    assert quality_grade(6.0) is None


# --- the tagger adapter (Lichess's own puzzles, from its tests) ------------------------------


@pytest.mark.parametrize(
    "theme,fen,line",
    [
        (
            "fork",
            "r3k2r/p2q1ppp/4pn2/1Qp5/8/4P3/PP1N1PPP/R3K2R w KQkq - 2 16",
            "b5c5 d7d2 e1d2 f6e4 d2e2 e4c5",
        ),
        (
            "hangingPiece",
            "r2qr1k1/1p3ppp/p1p2nb1/8/4P3/1P5P/PBQN1PP1/R3R1K1 w - - 1 17",
            "c2c4 d8d2 b2f6 g7f6",
        ),
        (
            "backRankMate",
            "r5k1/pQ3ppp/8/8/B1pp4/4q3/PP5P/5R1K b - - 0 26",
            "a8d8 b7f7 g8h8 f7f8 d8f8 f1f8",
        ),
        (
            "skewer",
            "1rr5/3k4/3bpp2/q5p1/PpRP3p/1P3N1P/1K1Q1PP1/7R w - - 2 25",
            "h1c1 d6f4 d2d3 f4c1",
        ),
        (
            "pin",
            "r2q1r1k/pp3pp1/2p2n1p/3PB2b/3P4/1B5P/P1PQ1PP1/R3R1K1 b - - 0 18",
            "f6d5 d2h6 h8g8 h6g7",
        ),
    ],
)
def test_allowed_tactics_are_named(theme, fen, line):
    first, *reply = line.split()
    assert theme in allowed_themes(chess.Board(fen), chess.Move.from_uci(first), reply)


def test_a_line_that_wins_less_than_two_pawns_names_nothing():
    board = chess.Board()  # 1. e4 d5 2. exd5: one pawn, not enough to call it a tactic
    board.push_uci("e2e4")
    assert winning_line(board, [chess.Move.from_uci("d7d5")]) is None
    assert allowed_themes(chess.Board(), chess.Move.from_uci("e2e4"), ["d7d5", "e4d5"]) == []


def test_a_gain_that_is_won_straight_back_does_not_count():
    # Bxf7+ grabs a pawn, Kxf7 takes the bishop back: the line is not a winning one.
    board = chess.Board("r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    assert winning_line(board, [chess.Move.from_uci(m) for m in ("c4f7", "e8f7")]) is None


def test_missed_tactics_use_the_opponents_previous_move_as_the_blunder():
    fen, line = (
        "r3k2r/p2q1ppp/4pn2/1Qp5/8/4P3/PP1N1PPP/R3K2R w KQkq - 2 16",
        "b5c5 d7d2 e1d2 f6e4 d2e2 e4c5",
    )
    first, *best = line.split()
    assert "fork" in missed_themes(chess.Board(fen), chess.Move.from_uci(first), best)


# --- notes, worded for the reader ------------------------------------------------------------


def test_refutation_note_for_the_mover_and_for_their_opponent():
    facts = RefutationFacts(
        rule="material", theme="hangingPiece", piece="bishop", before=55, after=20
    )
    assert refutation_note(facts, "black", "black") == "Hanging piece: this line wins your bishop."
    assert (
        refutation_note(facts, "black", "white") == "Hanging piece: this line wins Black's bishop."
    )


def test_other_refutation_rules():
    fork = RefutationFacts(
        rule="double_attack",
        theme="fork",
        reply="Nc7",
        targets=[("king", "e8"), ("rook", "a8")],
        before=50,
        after=10,
    )
    assert refutation_note(fork, "black", "black") == (
        "Fork: after Nc7, your king on e8 and your rook on a8 are both attacked."
    )
    mate = RefutationFacts(rule="mate", theme="backRankMate", before=60, after=0)
    assert refutation_note(mate, "white", "black") == "Back-rank mate: this line ends in checkmate."
    drop = RefutationFacts(rule="drop", before=55, after=30)
    assert (
        refutation_note(drop, "white", "white")
        == "This drops your winning chances from 55% to 30%."
    )
    assert (
        refutation_note(drop, "white", "black")
        == "This drops White's winning chances from 55% to 30%."
    )


def test_better_notes():
    good = BetterFacts(rule="advantage", move="18. Be2", eval="+1.2")
    assert better_note(good, "white", "white") == "18. Be2 keeps your advantage (+1.2)."
    assert better_note(good, "white", "black") == "18. Be2 keeps White's advantage (+1.2)."
    level = BetterFacts(rule="level", move="18… Be7", eval="+0.2")
    assert better_note(level, "black", "black") == "18… Be7 keeps the position level (+0.2)."


# --- openings and PGN ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slug,family",
    [
        ("Italian-Game-Two-Knights-Defense", "Italian Game"),
        ("Caro-Kann-Defense-Two-Knights-Attack-3...a6-4.d4-Bg4", "Caro-Kann Defense"),
        ("Queens-Gambit-Declined-Exchange-Variation", "Queen's Gambit"),
        ("Kings-Indian-Defense-Normal-Variation", "King's Indian Defense"),
        ("Nimzowitsch-Larsen-Attack", "Nimzowitsch-Larsen Attack"),
        ("Modern-Defense-with-1-d4", "Modern Defense"),
        ("Scandinavian-Defense-Mieses-Kotrc-Main-Line...6.Bc4-e6", "Scandinavian Defense"),
        ("Saragossa-Opening", "Saragossa Opening"),
        ("Undefined", "Unknown opening"),
    ],
)
def test_opening_families(slug, family):
    assert opening_family(f"https://www.chess.com/openings/{slug}") == family


def test_no_opening_link():
    assert opening_family(None) == "Unknown opening"


def test_parse_pgn():
    pgn = '[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0'
    game = parse_pgn(pgn)
    assert game.moves_uci == ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"]
    assert game.result == "1-0" and game.start_fen == chess.STARTING_FEN
    with pytest.raises(ValueError):
        parse_pgn('[Result "*"]\n\n1. e4 *')  # an unfinished game


# --- a whole game, with hand-written engine results ------------------------------------------


def line(pv: str, cp: int | None = None, mate: int | None = None) -> EngineLine:
    return EngineLine(cp=cp, mate=mate, pv=pv.split())


def test_scholars_mate_is_graded_end_to_end():
    moves = ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"]
    evals = [
        PositionEval(lines=[line("e2e4", 30)]),
        PositionEval(lines=[line("e7e5", 30)]),
        PositionEval(lines=[line("f1c4", 30)]),
        PositionEval(lines=[line("b8c6", 20)]),
        PositionEval(lines=[line("d1h5", 30)]),
        PositionEval(lines=[line("g7g6 c4f7", 0), line("d8e7", 40)]),  # Black to move: g6 holds
        PositionEval(lines=[line("h5f7", mate=1)]),  # after Nf6??: White mates in 1
        PositionEval(lines=[]),  # checkmate: the game is over
    ]
    result = analyse_game(chess.STARTING_FEN, moves, evals)
    blunder = result.moves[5]
    assert (blunder.san, blunder.grade, blunder.color) == ("Nf6", "blunder", "black")
    assert blunder.better_line[0] == "g6"
    assert blunder.refutation_line == ["Qxf7#"]
    assert blunder.refutation_facts.rule == "mate"
    assert better_note(blunder.better_facts, "black", "black").startswith("3… g6")
    assert result.moves[6].grade == "best"  # the engine's own move, even when it mates
    assert result.trace[-1] == 1000 and len(result.trace) == len(moves) + 1
    assert (
        result.error_counts["black"]["blunder"] == 1
        and result.error_counts["white"]["blunder"] == 0
    )
    assert result.moves[0].better_line is None  # lines only for errors


def test_great_needs_a_clearly_worse_second_move_and_more_than_one_legal_move():
    moves = ["e2e4"]
    evals = [
        PositionEval(lines=[line("e2e4", 300), line("d2d4", -100)]),
        PositionEval(lines=[line("e7e5", 300)]),
    ]
    assert analyse_game(chess.STARTING_FEN, moves, evals).moves[0].grade == "great"
    evals[0] = PositionEval(lines=[line("e2e4", 30), line("d2d4", 25)])
    assert analyse_game(chess.STARTING_FEN, moves, evals).moves[0].grade == "best"


# --- great and brilliant (tuned on 20 real club games) ---------------------------------------


def test_a_real_queen_sacrifice_counts_and_a_plain_capture_does_not():
    from app.analysis.tagging import is_sacrifice, offers_material

    # Lichess puzzle 1NHUV: after ...d6, Qxf7+! gives the queen (Rxf7) and Re8 mates.
    start = chess.Board("r1b2rk1/pppp1ppp/2n5/3Q2B1/2B5/2P2N2/P1q3PP/4RK1R b - - 1 14")
    previous = chess.Move.from_uci("d7d6")
    before = start.copy()
    before.push(previous)
    sac = chess.Move.from_uci("d5f7")
    assert offers_material(before, sac, ["f8f7", "e1e8"])
    assert is_sacrifice(start, previous, sac, ["f8f7", "e1e8"])
    plain = chess.Board()  # 1. e4 d5 2. exd5 Qxd5: a pawn trade offers nothing
    plain.push_uci("e2e4")
    plain.push_uci("d7d5")
    assert not offers_material(plain, chess.Move.from_uci("e4d5"), ["d8d5"])


@pytest.mark.parametrize(
    "fen,move,previous,obvious",
    [
        # escaping check (here by taking the checking queen)
        ("rnbqkbnr/ppp2Qpp/3p4/4p3/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 3", "e8f7", None, True),
        # recapturing where the opponent just captured: 1. e4 d5 2. exd5 Qxd5
        ("rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2", "d8d5", "e4d5", True),
        # taking a piece nothing defends: ...Bxg4
        ("rnbqkbnr/ppp1pppp/8/3p4/6Q1/4P3/PPPP1PPP/RNB1KBNR b KQkq - 1 2", "c8g4", None, True),
        # an ordinary move
        (chess.STARTING_FEN, "e2e4", None, False),
    ],
)
def test_obvious_moves_are_not_great(fen, move, previous, obvious):
    from app.analysis.grading import is_obvious

    prev = chess.Move.from_uci(previous) if previous else None
    assert is_obvious(chess.Board(fen), chess.Move.from_uci(move), prev) is obvious


def test_example_notes_say_whether_the_reply_itself_wins_the_piece():
    from app.analysis import example_note

    takes = RefutationFacts(
        rule="material", piece="queen", reply_takes="queen", before=60, after=10
    )
    assert example_note(takes, "17… Rxd8") == "17… Rxd8 wins your queen."
    later = RefutationFacts(
        rule="material",
        piece="queen",
        reply_takes="pawn",
        before=60,
        after=10,
        targets=[("king", "e1")],
    )
    assert example_note(later, "20… Bxf2+") == "20… Bxf2+ starts a line that wins your queen."

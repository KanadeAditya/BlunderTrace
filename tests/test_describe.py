import chess

from blundertrace.describe import (
    describe,
    game_phase,
    material_balance,
    open_files,
    pawn_structure,
)

IQP = "r1bq1rk1/pp2bppp/2n1pn2/3p4/3P4/2NB1N2/PP3PPP/R1BQ1RK1 w - - 0 10"
ROOK_ENDGAME = "r4rk1/pp3ppp/2p5/8/8/2P5/P1P2PPP/R4RK1 b - - 0 20"


def test_deterministic():
    board = chess.Board(IQP)
    assert describe(board) == describe(chess.Board(IQP))


def test_starting_position():
    text = describe(chess.Board())
    assert text.startswith("Opening.")
    assert "Material is equal." in text
    assert "open" not in text.replace("can still castle", "")  # no open files at the start


def test_phase():
    assert game_phase(chess.Board()) == "Opening"
    assert game_phase(chess.Board(ROOK_ENDGAME)) == "Endgame"
    late = chess.Board(IQP.replace(" 0 10", " 0 25"))
    assert game_phase(late) == "Middlegame"


def test_phase_counts_pieces_not_points():
    # Two queens + one rook = 3 pieces (23 points): an endgame, as Lichess labels it.
    queens = chess.Board("6k1/5ppp/8/8/8/8/q4PPP/3QR1K1 w - - 0 40")
    assert game_phase(queens) == "Endgame"


def test_material():
    assert material_balance(chess.Board(IQP)) == "Black is ahead by 1 point of material."
    no_queen = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert "White is ahead by 9 points" in material_balance(no_queen)


def test_isolated_pawn_and_files():
    board = chess.Board(IQP)
    assert "White has an isolated d-pawn." in pawn_structure(board)
    assert open_files(board) == ["The c-file is open.", "White has a half-open e-file."]


def test_doubled_and_passed():
    sentences = pawn_structure(chess.Board(ROOK_ENDGAME))
    assert any("doubled c-pawns" in s for s in sentences)
    passed = pawn_structure(chess.Board("8/5pk1/6p1/1P6/8/6P1/5PK1/8 w - - 0 45"))
    assert any("a passed b-pawn" in s for s in passed)


def test_backward_pawn():
    # White d3 cannot be supported by c/e pawns (both advanced); d4 is hit by Black's e5 pawn.
    board = chess.Board("4k3/8/8/2P1p3/4P3/3P4/8/4K3 w - - 0 30")
    assert any("a backward d-pawn" in s for s in pawn_structure(board))


def test_multiple_open_files_wording():
    board = chess.Board("4k3/pp6/8/8/8/8/PP6/4K3 w - - 0 40")
    assert open_files(board)[0] == "The c-, d-, e-, f-, g- and h-files are open."


def test_king_safety_and_mistake():
    text = describe(chess.Board(IQP), opening="Queen's Gambit Declined",
                    mistake="allowed a fork", mistake_by=chess.WHITE)
    assert "Queen's Gambit Declined." in text
    assert "White's king is on the kingside with an intact pawn shield." in text
    assert text.startswith("Mistake by White: allowed a fork. Opening.")


def test_brief():
    text = describe(chess.Board(IQP), opening="Queen's Gambit Declined",
                    mistake="allowed a fork", mistake_by=chess.WHITE, brief=True)
    assert text == "Mistake by White: allowed a fork. Opening. Queen's Gambit Declined."


def test_edge_king_shield():
    # King on h1 behind f2-g2-h2 is fully sheltered (used to be reported as weakened).
    h1 = chess.Board("r1bq1rk1/ppp2ppp/2n2n2/2b5/2B5/2N2N2/PPP2PPP/R1BQ1R1K w - - 0 20")
    assert "White's king is on the kingside with an intact pawn shield." in describe(h1)
    # King on h8 with only g7+h7: f-pawn gone -> weakened.
    h8 = chess.Board("r1bq1r1k/ppp3pp/2n2n2/2b5/2B5/2N2N2/PPP2PPP/R1BQ1RK1 w - - 0 20")
    assert "Black's king is on the kingside with a weakened pawn shield." in describe(h8)


def test_king_stuck_in_centre_and_exposed():
    stuck = chess.Board("r1bqk2r/ppp2ppp/2n2n2/2b5/2B5/2N2N2/PPP2PPP/R1BQK2R w - - 0 20")  # no castling rights
    text = describe(stuck)
    assert "White's king is stuck in the centre and can no longer castle." in text
    exposed = chess.Board("r1bq1rk1/ppp2ppp/2n2n2/2b5/2B5/2N2NK1/PPP2PPP/R1BQ1R2 w - - 0 20")
    assert "White's king is exposed, away from its back rank." in describe(exposed)


def test_endgame_has_no_king_location():
    text = describe(chess.Board(ROOK_ENDGAME))
    assert "king" not in text

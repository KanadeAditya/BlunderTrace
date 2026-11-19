"""The Stockfish wrapper and the whole chess pipeline, with the real engine at a small search."""

import shutil

import chess
import pytest

from app.analysis import PositionEval, analyse_game, refutation_note
from app.engine import Stockfish

pytestmark = pytest.mark.skipif(shutil.which("stockfish") is None, reason="Stockfish not installed")

NODES = 50_000  # small: fast, and still plenty for one-move blunders


@pytest.fixture
async def engine():
    sf = Stockfish(nodes=NODES)
    await sf.start()
    yield sf
    await sf.stop()


async def test_reports_its_version_and_two_lines(engine):
    assert engine.version.startswith("Stockfish")
    position = await engine.evaluate(chess.Board(), object())
    assert len(position.lines) == 2
    assert all(line.pv for line in position.lines)


async def test_a_finished_game_needs_no_engine(engine):
    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert mated.is_checkmate()
    assert (await engine.evaluate(mated, object())).lines == []


async def test_the_same_game_gives_the_same_results_every_time(engine):
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"]
    first = await engine.evaluate_game(chess.STARTING_FEN, moves)
    second = await engine.evaluate_game(chess.STARTING_FEN, moves)
    assert first == second


async def test_hanging_the_queen_is_a_blunder_named_hanging_piece(engine):
    moves = ["e2e4", "e7e5", "g1f3", "d8h4"]  # 2... Qh4?? lets the knight take the queen
    positions = await engine.evaluate_game(chess.STARTING_FEN, moves)
    evals = [PositionEval.model_validate(p, from_attributes=True) for p in positions]
    result = analyse_game(chess.STARTING_FEN, moves, evals)
    queen_move = result.moves[3]
    assert (queen_move.san, queen_move.grade) == ("Qh4", "blunder")
    assert "hangingPiece" in queen_move.themes
    assert queen_move.refutation_line[0] == "Nxh4"
    assert refutation_note(queen_move.refutation_facts, "black", "black") == (
        "Hanging piece: this line wins your queen."
    )
    assert result.error_counts["black"]["blunder"] == 1

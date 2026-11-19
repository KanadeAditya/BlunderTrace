"""The weakness-card rules from the final check (gaps 2 and 3)."""

from app.analysis.models import MoveRecord
from app.analysis.patterns import missed_tactics, pick_examples, top_weaknesses


def move(grade: str, themes=(), missed=(), loss: float = 20.0, ply: int = 1) -> MoveRecord:
    return MoveRecord(
        ply=ply,
        move_number=1,
        color="white",
        san="e4",
        fen_after="",
        eval={"cp": 0},
        grade=grade,
        themes=list(themes),
        missed_themes=list(missed),
        uci="e2e4",
        win_before=50,
        win_after=30,
        loss=loss,
    )


def test_games_beat_times():
    # Hanging piece 6 times in 2 games; fork once in each of 4 games: fork is the habit.
    games = {
        "g1": [move("blunder", ["hangingPiece"])] * 3,
        "g2": [move("blunder", ["hangingPiece"])] * 3 + [move("mistake", ["fork"])],
        "g3": [move("mistake", ["fork"])],
        "g4": [move("blunder", ["fork"])],
        "g5": [move("blunder", ["fork"])],
    }
    top = top_weaknesses(games)
    assert [(c.theme, c.games, c.times) for c in top] == [("fork", 4, 4), ("hangingPiece", 2, 6)]


def test_ties_go_to_more_times():
    games = {
        "g1": [move("blunder", ["pin"]), move("blunder", ["pin"]), move("blunder", ["skewer"])]
    }
    assert [c.theme for c in top_weaknesses(games)] == ["pin", "skewer"]


def test_inaccuracies_only_fill_missing_cards():
    games = {
        "g1": [
            move("blunder", ["fork"]),
            move("inaccuracy", ["pin"]),
            move("inaccuracy", ["fork"]),
        ],
        "g2": [move("inaccuracy", ["skewer"]), move("inaccuracy", ["exposedKing"])],
    }
    assert [c.theme for c in top_weaknesses(games)] == ["fork", "pin", "skewer"]
    full = {
        "g1": [move("blunder", ["fork"]), move("mistake", ["pin"]), move("blunder", ["skewer"])],
        "g2": [move("inaccuracy", ["hangingPiece"])] * 5,
    }
    assert "hangingPiece" not in [c.theme for c in top_weaknesses(full)]


def test_fewer_cards_only_when_there_are_fewer_tactics():
    assert [c.theme for c in top_weaknesses({"g1": [move("blunder", ["fork"])]})] == ["fork"]
    assert top_weaknesses({"g1": [move("good")]}) == []


def test_missed_tactics_count_times_whatever_the_label():
    games = {"g1": [move("miss", missed=["fork"]), move("blunder", ["pin"], missed=["fork"])]}
    assert [(c.theme, c.times) for c in missed_tactics(games)] == [("fork", 2)]


def test_examples_come_from_different_games_first():
    games = {
        "g1": [
            move("blunder", ["fork"], loss=40, ply=1),
            move("blunder", ["fork"], loss=35, ply=2),
        ],
        "g2": [move("blunder", ["fork"], loss=20, ply=3)],
    }
    chosen = pick_examples(top_weaknesses(games)[0])
    assert [(g, m.loss) for g, m in chosen] == [("g1", 40), ("g2", 20), ("g1", 35)]


def test_quiet_and_defensive_moves_are_never_cards_but_still_missed_tactics():
    games = {
        "g1": [move("blunder", ["quietMove"]), move("blunder", ["defensiveMove", "fork"])],
        "g2": [move("miss", missed=["quietMove"])],
    }
    assert [c.theme for c in top_weaknesses(games)] == ["fork"]
    assert [c.theme for c in missed_tactics(games)] == ["quietMove"]

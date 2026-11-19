"""The shapes analysis works with: engine results in, one record per half-move out.

Engine scores are always from White's point of view, as in docs/API.md ("Evaluation").
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Color = Literal["white", "black"]
Grade = Literal[
    "brilliant", "great", "best", "excellent", "good", "inaccuracy", "mistake", "blunder", "miss"
]
ERROR_GRADES: tuple[Grade, ...] = ("inaccuracy", "mistake", "blunder", "miss")

# The 11 weakness themes (Lichess puzzle-theme keys), in the order a note names them first.
THEMES: tuple[str, ...] = (
    "backRankMate",
    "fork",
    "pin",
    "skewer",
    "discoveredAttack",
    "hangingPiece",
    "trappedPiece",
    "exposedKing",
    "advancedPawn",
    "quietMove",
    "defensiveMove",
)
THEME_NAMES: dict[str, str] = {
    "backRankMate": "Back-rank mate",
    "fork": "Fork",
    "pin": "Pin",
    "skewer": "Skewer",
    "discoveredAttack": "Discovered attack",
    "hangingPiece": "Hanging piece",
    "trappedPiece": "Trapped piece",
    "exposedKing": "Exposed king",
    "advancedPawn": "Advanced pawn",
    "quietMove": "Quiet move",
    "defensiveMove": "Defensive move",
}


class EngineLine(BaseModel):
    """One of the engine's best lines from a position, scored from White's point of view."""

    model_config = ConfigDict(from_attributes=True)  # accepts the engine module's own objects

    cp: int | None = None
    mate: int | None = None  # moves to mate; positive = White mates
    pv: list[str]  # the line, as UCI moves ("e2e4")


class PositionEval(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lines: list[EngineLine]  # best first; empty when the game is over in this position


class Eval(BaseModel):
    cp: int | None = None
    mate: int | None = None


class RefutationFacts(BaseModel):
    """What "Show why it's bad" is about. Worded into a sentence only when the game is read."""

    rule: Literal["mate", "material", "double_attack", "drop"]
    theme: str | None = None
    piece: str | None = None  # "material": the most valuable piece lost
    reply_takes: str | None = None  # the piece the opponent's reply itself captures, if any
    reply: str | None = None  # "double_attack": the opponent's reply, in SAN
    targets: list[tuple[str, str]] = []  # "double_attack": (piece, square), most valuable first
    before: int  # the mover's winning chances before the move, in %
    after: int  # ... and after it


class BetterFacts(BaseModel):
    """What "Show better move" is about."""

    rule: Literal["advantage", "level", "damage"]
    move: str  # with its move number, e.g. "18. Be2" or "18… Be2"
    eval: str  # e.g. "+1.2" (White's point of view) or "#3"


class MoveRecord(BaseModel):
    """One half-move as stored in games.moves. API fields first, then internal ones."""

    ply: int
    move_number: int
    color: Color
    san: str
    fen_after: str
    eval: Eval  # after the move, White's point of view
    grade: Grade | None
    themes: list[str] = []  # tactics this move allowed (errors only)
    better_line: list[str] | None = None
    refutation_line: list[str] | None = None
    refutation_arrows: list[tuple[str, str]] | None = None
    better_facts: BetterFacts | None = None
    refutation_facts: RefutationFacts | None = None
    # Internal
    uci: str
    best_uci: str | None = None
    win_before: float
    win_after: float
    loss: float
    second_gap: float | None = None
    missed_themes: list[str] = []  # winning tactics the better line had


class GameAnalysis(BaseModel):
    moves: list[MoveRecord]
    trace: list[int]  # White's eval in centipawns after each half-move, start included, capped
    error_counts: dict[Color, dict[str, int]]

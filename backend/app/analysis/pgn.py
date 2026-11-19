"""Reading a chess.com game: its PGN (moves, starting position) and its opening family."""

import io
import re
from dataclasses import dataclass

import chess
import chess.pgn


@dataclass
class ParsedGame:
    start_fen: str
    moves_uci: list[str]
    result: str  # "1-0" / "0-1" / "1/2-1/2"


def parse_pgn(pgn: str) -> ParsedGame:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("not a PGN")
    if game.errors:  # python-chess collects problems instead of raising
        raise ValueError(f"PGN problem: {game.errors[0]}")
    result = game.headers.get("Result", "*")
    if result not in ("1-0", "0-1", "1/2-1/2"):
        raise ValueError(f"unfinished game ({result})")
    return ParsedGame(
        start_fen=game.board().fen(),
        moves_uci=[m.uci() for m in game.mainline_moves()],
        result=result,
    )


# Words that end an opening's family name in chess.com's links ("Italian-Game-Two-Knights-...").
_FAMILY_END = {"Defense", "Opening", "Game", "Gambit", "Attack", "System"}
_POSSESSIVE = {
    "Kings": "King's",
    "Queens": "Queen's",
    "Bishops": "Bishop's",
    "Petrovs": "Petrov's",
    "Alekhines": "Alekhine's",
    "Owens": "Owen's",
    "Birds": "Bird's",
    "Larsens": "Larsen's",
    "Philidors": "Philidor's",
}
_HYPHENATED = {
    "Caro Kann": "Caro-Kann",
    "Nimzowitsch Larsen": "Nimzowitsch-Larsen",
    "Nimzo Larsen": "Nimzo-Larsen",
    "Nimzo Indian": "Nimzo-Indian",
    "Bogo Indian": "Bogo-Indian",
}
UNKNOWN_OPENING = "Unknown opening"


def opening_family(eco_url: str | None) -> str:
    """ ".../openings/Italian-Game-Two-Knights-Defense" -> "Italian Game"."""
    if not eco_url or "/openings/" not in eco_url:
        return UNKNOWN_OPENING
    slug = eco_url.rstrip("/").split("/openings/")[-1]
    words = [w for w in re.split(r"[-]", slug.split("...")[0]) if w and not w[0].isdigit()]
    if not words or words[0] == "Undefined":
        return UNKNOWN_OPENING
    family: list[str] = []
    for word in words:
        family.append(_POSSESSIVE.get(word, word))
        if word in _FAMILY_END:
            break
    name = " ".join(family[:5])
    for spaced, hyphenated in _HYPHENATED.items():
        name = name.replace(spaced, hyphenated)
    return name

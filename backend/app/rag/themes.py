"""One fixed search per weakness theme (docs/BACKEND.md section 8).

- `query`: the question searched **by meaning** (its vector is made once, at library build time).
  It asks about the idea and how to avoid it, never about a position: our research showed
  embeddings understand language, not chess positions.
- `keywords`: what the **word search** looks for, any of them (gap 7 of the final check). The
  question itself can't be used there: Postgres would require every one of its words.

Drafted and checked by Claude during the build; reported in the end-of-build findings.
"""

CONCEPT_QUERIES: dict[str, tuple[str, list[str]]] = {
    "fork": (
        "How do I avoid allowing a fork, where one enemy piece attacks two of my pieces at once?",
        ["fork", "double attack", "attacks two", "knight fork", "family fork"],
    ),
    "pin": (
        "How do I avoid getting my pieces pinned, and how do I deal with a pin?",
        ["pin", "pinned", "absolute pin", "relative pin", "unpin"],
    ),
    "skewer": (
        "How do I avoid a skewer, where my valuable piece is attacked and the piece behind it"
        " is lost?",
        ["skewer", "skewered", "x-ray"],
    ),
    "discoveredAttack": (
        "How do I spot and avoid discovered attacks and discovered checks?",
        ["discovered attack", "discovered check", "unmask", "uncover"],
    ),
    "hangingPiece": (
        "How do I stop leaving pieces undefended so my opponent can capture them for free?",
        ["hanging", "undefended", "unprotected", "en prise", "loose piece"],
    ),
    "backRankMate": (
        "How do I avoid a back-rank checkmate and give my king an escape square?",
        ["back rank", "back-rank", "luft", "escape square", "corridor mate"],
    ),
    "trappedPiece": (
        "How do I avoid getting a piece trapped with no safe squares to escape to?",
        ["trapped", "trapping", "no escape", "no retreat", "domination"],
    ),
    "exposedKing": (
        "How do I keep my king safe and avoid attacks against an exposed king?",
        ["king safety", "exposed king", "pawn shield", "pawn cover", "castling"],
    ),
    "advancedPawn": (
        "How do I stop an advanced passed pawn before it promotes?",
        ["passed pawn", "promotion", "promote", "blockade", "queening"],
    ),
    "quietMove": (
        "What is a quiet move, and how do I notice quiet threats that are not checks or captures?",
        ["quiet move", "prophylaxis", "threat", "zwischenzug"],
    ),
    "defensiveMove": (
        "How do I find the one defensive move that holds my position when I am under attack?",
        ["defence", "defense", "defensive", "only move", "counterattack"],
    ),
}

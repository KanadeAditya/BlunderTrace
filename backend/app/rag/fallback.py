"""Fixed card text, used when the AI can't write a card (no key, both providers down, nothing
relevant found, or the move check failed twice). A report never fails because of the AI.

- "Why it happens": Lichess's own definition of the tactic, cited.
- "How to avoid it": one short, practical habit per theme, written for club players.
"""

from dataclasses import dataclass

LICHESS_THEMES_URL = "https://lichess.org/training/{theme}"

# Lichess puzzle-theme definitions (lichess.org/training/themes). Fork's entry is missing from
# the research corpus, so its definition is Lichess's own wording, added here.
DEFINITIONS: dict[str, tuple[str, str]] = {
    "fork": ("Fork", "A move where the moved piece attacks two opponent pieces at once."),
    "pin": (
        "Pin",
        "A tactic involving pins, where a piece is unable to move without revealing "
        "an attack on a higher value piece.",
    ),
    "skewer": (
        "Skewer",
        "A motif involving a high value piece being attacked, moving out the "
        "way, and allowing a lower value piece behind it to be captured or attacked, the "
        "inverse of a pin.",
    ),
    "discoveredAttack": (
        "Discovered attack",
        "Moving a piece (such as a knight), that previously "
        "blocked an attack by a long range piece (such as a rook), out of the way "
        "of that piece.",
    ),
    "hangingPiece": (
        "Hanging piece",
        "A tactic involving an opponent piece being undefended or "
        "insufficiently defended and free to capture.",
    ),
    "backRankMate": (
        "Back rank mate",
        "Checkmate the king on the home rank, when it is trapped there by its own pieces.",
    ),
    "trappedPiece": (
        "Trapped piece",
        "A piece is unable to escape capture as it has limited moves.",
    ),
    "exposedKing": (
        "Exposed king",
        "A tactic involving a king with few defenders around it, often leading to checkmate.",
    ),
    "advancedPawn": (
        "Advanced pawn",
        "One of your pawns is deep into the opponent position, maybe threatening to promote.",
    ),
    "quietMove": (
        "Quiet move",
        "A move that does not check, capture, or create an immediate "
        "threat to capture. Instead, it prepares a hidden and unavoidable threat for a "
        "later move.",
    ),
    "defensiveMove": (
        "Defensive move",
        "A precise move or sequence of moves that is needed to "
        "avoid losing material or another advantage.",
    ),
}

TIPS: dict[str, str] = {
    "fork": "Before every move, look at where your opponent's knights and queen can go next, and "
    "ask: *could one move attack two of my pieces at once?* Keep your pieces defended and off "
    "squares a single piece can hit together.",
    "pin": "Before moving a piece, check what stands behind it on the same line: *if it moves, "
    "does it uncover my king or queen?* Step valuable pieces off lines your opponent's bishops, "
    "rooks and queen can use.",
    "skewer": "Don't line up your king or queen in front of another piece on an open line. Ask: "
    "*if my big piece is chased away, what gets taken behind it?*",
    "discoveredAttack": "Watch your opponent's long-range pieces hiding behind their own pieces. "
    "Ask: *if that blocking piece moves, what does the hidden rook, bishop or queen hit?*",
    "hangingPiece": "Before every move, ask one question: *after this, what can my opponent "
    "capture — and is it defended?* Count the attackers and defenders of every piece you move.",
    "backRankMate": "Give your king an escape square early (*luft*), with a pawn move like h3, "
    "and keep a rook or queen guarding your back rank until it's safe.",
    "trappedPiece": "Before sending a piece deep into enemy territory, plan its way back. Ask: "
    "*if it's attacked here, where can it go?*",
    "exposedKing": "Leave the pawns in front of your castled king where they are unless you have "
    "a clear reason, and bring defenders back when enemy pieces gather near your king.",
    "advancedPawn": "Stop passed pawns early: put a piece directly in front of them (*a "
    "blockade*) and count how many moves they need to promote.",
    "quietMove": "When nothing is attacked, still ask *what is my opponent threatening next?* "
    "Quiet moves set up threats that land a move later.",
    "defensiveMove": "When you're under attack, look for the one move that holds everything "
    "together before reaching for a counter-attack.",
}


@dataclass
class CardText:
    why: str
    how_to_avoid: str
    sources: list[dict[str, str]]


def fallback_card(theme: str) -> CardText:
    name, definition = DEFINITIONS[theme]
    return CardText(
        why=f"{definition}[1]",
        how_to_avoid=TIPS[theme],
        sources=[
            {
                "title": "Lichess puzzle themes",
                "url": LICHESS_THEMES_URL.format(theme=theme),
                "passage": f"{name}: {definition}",
            }
        ],
    )

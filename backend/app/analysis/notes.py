"""Turning stored note facts into sentences, worded for whoever is reading.

A game is shared by both players' reports, so the same move is "your move" for one reader and "your
opponent's move" for the other. The sentence is built when the game is read: "your" for the
reader's own moves, "White's" / "Black's" for the opponent's, as the frontend words its own text.
"""

from app.analysis.models import THEME_NAMES, BetterFacts, Color, RefutationFacts


def _owner(mover: Color, reader: Color) -> str:
    if mover == reader:
        return "your"
    return "White's" if mover == "white" else "Black's"


def refutation_note(facts: RefutationFacts, mover: Color, reader: Color) -> str:
    who = _owner(mover, reader)
    prefix = f"{THEME_NAMES[facts.theme]}: " if facts.theme in THEME_NAMES else ""
    if facts.rule == "mate":
        return f"{prefix}this line ends in checkmate."
    if facts.rule == "material":
        return f"{prefix}this line wins {who} {facts.piece}."
    if facts.rule == "double_attack" and len(facts.targets) >= 2:
        (p1, s1), (p2, s2) = facts.targets[:2]
        targets = f"{who} {p1} on {s1} and {who} {p2} on {s2}"
        return f"{prefix}after {facts.reply}, {targets} are both attacked."
    return f"This drops {who} winning chances from {facts.before}% to {facts.after}%."


def better_note(facts: BetterFacts, mover: Color, reader: Color) -> str:
    if facts.rule == "advantage":
        return f"{facts.move} keeps {_owner(mover, reader)} advantage ({facts.eval})."
    if facts.rule == "level":
        return f"{facts.move} keeps the position level ({facts.eval})."
    return f"{facts.move} limits the damage ({facts.eval})."


GLYPHS = {
    "brilliant": "!!",
    "great": "!",
    "inaccuracy": "?!",
    "mistake": "?",
    "blunder": "??",
    "miss": "?",
}


def example_note(facts: RefutationFacts, reply: str) -> str:
    """The one sentence under a report example, about the opponent's reply (always the user's own
    move, so always "your"). `reply` is labelled, e.g. "4… Qg5!" (a glyph only if it was played)."""
    if facts.rule == "mate":
        return f"{reply} leads to checkmate."
    if len(facts.targets) >= 2:
        (p1, s1), (p2, s2) = facts.targets[:2]
        return f"{reply} attacks your {p1} on {s1} and your {p2} on {s2}."
    if facts.rule == "material" and facts.piece:
        if facts.reply_takes == facts.piece:
            return f"{reply} wins your {facts.piece}."
        return f"{reply} starts a line that wins your {facts.piece}."
    if facts.targets:
        piece, square = facts.targets[0]
        return f"{reply} attacks your {piece} on {square}."
    return f"After {reply}, your winning chances drop from {facts.before}% to {facts.after}%."

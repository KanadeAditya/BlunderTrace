"""Counting the user's repeated mistakes: the top 3 weakness cards and the missed tactics.

The rules (gaps 2 and 3 of the final check, docs/BACKEND.md section 7):
- A card's count is the number of **games** in which the user allowed the tactic at least once;
  ties go to the tactic that happened more times.
- Cards come from the user's blunders and mistakes. If those give fewer than 3 tactics, inaccuracies
  that allowed a tactic fill the remaining slots.
- Missed tactics are counted in **times**, from every user error whose better line had one,
  whatever the move's label.
- "Quiet move" and "defensive move" never become cards. As a tactic the user *allowed*, they only
  describe the opponent's key move, not a habit of the user's (checked on real games). They still
  count as missed tactics, where they do mean something: "you missed a quiet winning move".
"""

from dataclasses import dataclass, field

from app.analysis.models import THEMES, MoveRecord

MAIN_GRADES = ("blunder", "mistake")
FILL_GRADES = ("inaccuracy",)
NOT_A_CARD = {"quietMove", "defensiveMove"}


@dataclass
class ThemeCount:
    theme: str
    games: int = 0
    times: int = 0
    moments: list[tuple[str, MoveRecord]] = field(default_factory=list)  # (game id, move)


def _count(
    moves_by_game: dict[str, list[MoveRecord]], grades: tuple[str, ...]
) -> dict[str, ThemeCount]:
    counts: dict[str, ThemeCount] = {}
    for game_id, moves in moves_by_game.items():
        seen: set[str] = set()
        for move in moves:
            if move.grade not in grades:
                continue
            for theme in move.themes:
                if theme in NOT_A_CARD:
                    continue
                entry = counts.setdefault(theme, ThemeCount(theme))
                entry.times += 1
                entry.moments.append((game_id, move))
                if theme not in seen:
                    entry.games += 1
                    seen.add(theme)
    return counts


def _ranked(counts: dict[str, ThemeCount]) -> list[ThemeCount]:
    return sorted(counts.values(), key=lambda c: (-c.games, -c.times, THEMES.index(c.theme)))


def top_weaknesses(moves_by_game: dict[str, list[MoveRecord]], limit: int = 3) -> list[ThemeCount]:
    """`moves_by_game`: only the user's own moves, per game."""
    ranked = _ranked(_count(moves_by_game, MAIN_GRADES))
    if len(ranked) < limit:
        taken = {c.theme for c in ranked}
        fill = [c for c in _ranked(_count(moves_by_game, FILL_GRADES)) if c.theme not in taken]
        ranked += fill
    return ranked[:limit]


def missed_tactics(moves_by_game: dict[str, list[MoveRecord]]) -> list[ThemeCount]:
    counts: dict[str, ThemeCount] = {}
    for game_id, moves in moves_by_game.items():
        for move in moves:
            for theme in move.missed_themes:
                entry = counts.setdefault(theme, ThemeCount(theme))
                entry.times += 1
                entry.moments.append((game_id, move))
    return sorted(counts.values(), key=lambda c: (-c.times, THEMES.index(c.theme)))


def pick_examples(count: ThemeCount, limit: int = 3) -> list[tuple[str, MoveRecord]]:
    """The biggest losses, one per game first; more from the same game only if needed."""
    by_loss = sorted(count.moments, key=lambda m: -m[1].loss)
    chosen, used_games = [], set()
    for game_id, move in by_loss:
        if game_id not in used_games:
            chosen.append((game_id, move))
            used_games.add(game_id)
    for moment in by_loss:
        if len(chosen) >= limit:
            break
        if moment not in chosen:
            chosen.append(moment)
    return chosen[:limit]

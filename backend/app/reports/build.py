"""`build_report`: the top 3 weakness cards, missed tactics, openings and the summary.

Runs once every game of the report is finished (done or skipped). A report fails only if more than
half of its games couldn't be analysed; the AI never fails it (cards fall back to fixed text).
"""

import logging
from collections import defaultdict

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from app.analysis import (
    GLYPHS,
    THEME_NAMES,
    UNKNOWN_OPENING,
    MoveRecord,
    example_note,
    missed_tactics,
    pick_examples,
    top_weaknesses,
)
from app.db import get_pool
from app.logs import bind
from app.rag import fallback_card
from app.reports.complete import fail_report
from app.reports.models import (
    Example,
    OpeningScore,
    ReportResult,
    Source,
    Summary,
    ThemeCount,
    Weakness,
)

log = logging.getLogger(__name__)

MOVES = TypeAdapter(list[MoveRecord])
MIN_OPENING_GAMES = 4  # "Your score in each opening you played at least 4 times."

_GAMES = """
SELECT rg.position, rg.user_color, g.id, g.status, g.moves, g.white, g.black, g.result,
       g.opening, g.start_fen, g.error_counts
  FROM report_games rg JOIN games g ON g.id = rg.game_id
 WHERE rg.report_id = %s
 ORDER BY rg.position
"""


def _outcome(result: str, color: str) -> str:
    if result == "1/2-1/2":
        return "draw"
    return "win" if (result == "1-0") == (color == "white") else "loss"


def _example(game: dict, move: MoveRecord, all_moves: list[MoveRecord]) -> Example:
    index = move.ply - 1
    fen_before = all_moves[index - 1].fen_after if index > 0 else game["start_fen"]
    reply = (move.refutation_line or [""])[0]
    played_next = all_moves[index + 1] if index + 1 < len(all_moves) else None
    # The reply gets a glyph only if the opponent actually played it (fix 5 of the second check).
    glyph = (
        GLYPHS.get(played_next.grade or "", "") if played_next and played_next.san == reply else ""
    )
    number = f"{move.move_number}…" if move.color == "white" else f"{move.move_number + 1}."
    note = (
        example_note(move.refutation_facts, f"{number} {reply}{glyph}")
        if move.refutation_facts
        else ""
    )
    return Example(
        game_id=game["id"],
        ply=move.ply,
        move_number=move.move_number,
        color=move.color,
        opponent=game["black"] if move.color == "white" else game["white"],
        fen_before=fen_before,
        played=move.san,
        grade=move.grade or "blunder",
        better=(move.better_line or [None])[0],
        punishing_line=move.refutation_line or [],
        note=note,
        arrows=move.refutation_arrows or [],
    )


def _openings(games: list[dict]) -> list[OpeningScore]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for g in games:
        if g["opening"] != UNKNOWN_OPENING:
            groups[(g["opening"], g["user_color"])].append(_outcome(g["result"], g["user_color"]))
    scores = []
    for (name, color), outcomes in groups.items():
        if len(outcomes) >= MIN_OPENING_GAMES:
            wins, draws = outcomes.count("win"), outcomes.count("draw")
            scores.append(
                OpeningScore(
                    name=name,
                    color=color,
                    games=len(outcomes),
                    wins=wins,
                    draws=draws,
                    losses=outcomes.count("loss"),
                    score=round((wins + draws / 2) / len(outcomes), 2),
                )
            )
    return sorted(scores, key=lambda s: -s.games)


def _summary(games: list[dict]) -> Summary:
    outcomes = [_outcome(g["result"], g["user_color"]) for g in games]
    totals: dict[str, int] = defaultdict(int)
    for g in games:
        for grade, n in g["error_counts"][g["user_color"]].items():
            totals[grade] += n
    per_game = lambda grade: round(totals[grade] / len(games), 1)  # noqa: E731
    return Summary(
        games=len(games),
        wins=outcomes.count("win"),
        draws=outcomes.count("draw"),
        losses=outcomes.count("loss"),
        blunders_per_game=per_game("blunder"),
        mistakes_per_game=per_game("mistake"),
        misses_per_game=per_game("miss"),
    )


async def build_report(report_id: str) -> None:
    async with get_pool().connection() as conn:
        report = await (
            await conn.execute("SELECT status, notes FROM reports WHERE id = %s", (report_id,))
        ).fetchone()
        if report is None or report["status"] != "running":
            return  # already built (or failed): building twice changes nothing
        rows = await (await conn.execute(_GAMES, (report_id,))).fetchall()

    with bind(report_id=report_id):
        done = [r for r in rows if r["status"] == "done"]
        skipped = len(rows) - len(done)
        if not rows or skipped * 2 > len(rows):
            detail = "Most of these games couldn't be analysed. Please try again later."
            await fail_report(report_id, "analysis_failed", detail)
            return

        games_by_id = {g["id"]: g for g in done}
        all_moves = {g["id"]: MOVES.validate_python(g["moves"]) for g in done}
        mine = {
            gid: [m for m in moves if m.color == games_by_id[gid]["user_color"]]
            for gid, moves in all_moves.items()
        }

        weaknesses = []
        for count in top_weaknesses(mine):
            text = fallback_card(count.theme)  # build step 8 replaces this with the AI's card
            weaknesses.append(
                Weakness(
                    theme=count.theme,
                    name=THEME_NAMES[count.theme],
                    count=count.games,
                    why=text.why,
                    how_to_avoid=text.how_to_avoid,
                    examples=[
                        _example(games_by_id[g], m, all_moves[g]) for g, m in pick_examples(count)
                    ],
                    sources=[Source(**s) for s in text.sources],
                )
            )
        missed = [
            ThemeCount(theme=c.theme, name=THEME_NAMES[c.theme], count=c.times)
            for c in missed_tactics(mine)
        ]
        result = ReportResult(
            summary=_summary(done),
            weaknesses=weaknesses,
            missed_tactics=missed,
            openings=_openings(done),
        )
        notes = list(report["notes"])
        if skipped:
            were = (
                "game couldn't be analysed and was"
                if skipped == 1
                else "games couldn't be analysed and were"
            )
            notes.append(f"{skipped} {were} skipped.")
        async with get_pool().connection() as conn:
            await conn.execute(
                "UPDATE reports SET status = 'done', result = %s, notes = %s, finished_at = now()"
                " WHERE id = %s AND status = 'running'",
                (Jsonb(result.model_dump(mode="json")), Jsonb(notes), report_id),
            )
        log.info("report built", extra={"games": len(done), "cards": len(weaknesses)})

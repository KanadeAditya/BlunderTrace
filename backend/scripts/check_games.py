"""Dev check: run the whole chess pipeline on saved games and print what the report would find.

    PYTHONPATH=. uv run python scripts/check_games.py <games.json> <username> [--engines 2]

<games.json> is the engine-timing format: {"games": [{"url", "pgn", "time_class"}, ...]}.
Prints the grade spread, the top-3 weakness cards (with the gap 2 rules), missed tactics, every
"quiet move" / "defensive move" moment, and a few notes, so the rules can be checked on real games.
No database and no network: just Stockfish and the analysis code.
"""

import argparse
import asyncio
import io
import json
import time
from collections import Counter
from pathlib import Path

import chess.pgn

from app.analysis import PositionEval, analyse_game, better_note, parse_pgn, refutation_note
from app.analysis.patterns import missed_tactics, pick_examples, top_weaknesses
from app.engine import Stockfish


def user_color(pgn: str, username: str) -> str:
    headers = chess.pgn.read_headers(io.StringIO(pgn))
    return "white" if headers.get("White", "").lower() == username.lower() else "black"


async def analyse_all(
    games: list[dict], engines: int, nodes: int, cache: dict
) -> list[tuple[dict, object]]:
    """Analyse every game. Engine results are kept in `cache` (by game URL), so re-running the
    script after a rule change re-grades instantly instead of running Stockfish again."""
    queue: asyncio.Queue = asyncio.Queue()
    results: dict[int, tuple[dict, object]] = {}
    for i, game in enumerate(games):
        if game["url"] in cache:
            parsed = parse_pgn(game["pgn"])
            evals = [PositionEval.model_validate(p) for p in cache[game["url"]]]
            results[i] = (game, analyse_game(parsed.start_fen, parsed.moves_uci, evals))
        else:
            queue.put_nowait((i, game))

    async def worker() -> None:
        sf = Stockfish(nodes=nodes)
        await sf.start()
        try:
            while not queue.empty():
                i, game = queue.get_nowait()
                parsed = parse_pgn(game["pgn"])
                started = time.perf_counter()
                positions = await sf.evaluate_game(parsed.start_fen, parsed.moves_uci)
                evals = [PositionEval.model_validate(p, from_attributes=True) for p in positions]
                cache[game["url"]] = [e.model_dump() for e in evals]
                analysis = analyse_game(parsed.start_fen, parsed.moves_uci, evals)
                took = time.perf_counter() - started
                print(
                    f"game {i + 1:2}: {len(parsed.moves_uci):3} plies in {took:5.1f} s", flush=True
                )
                results[i] = (game, analysis)
        finally:
            await sf.stop()

    await asyncio.gather(*(worker() for _ in range(engines)))
    return [results[i] for i in sorted(results)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("games")
    parser.add_argument("username")
    parser.add_argument("--engines", type=int, default=2)
    parser.add_argument("--nodes", type=int, default=100_000)
    parser.add_argument("--cache", help="JSON file to keep engine results in between runs")
    args = parser.parse_args()
    games = json.loads(Path(args.games).read_text())["games"]
    cache_file = Path(args.cache) if args.cache else None
    cache = json.loads(cache_file.read_text()) if cache_file and cache_file.exists() else {}

    started = time.perf_counter()
    results = asyncio.run(analyse_all(games, args.engines, args.nodes, cache))
    if cache_file:
        cache_file.write_text(json.dumps(cache))
    took = time.perf_counter() - started
    print(f"\n{len(results)} games in {took:.0f} s with {args.engines} engines")

    user_moves = {}
    grades: Counter = Counter()
    quiet_defensive = []
    for i, (game, analysis) in enumerate(results):
        color = user_color(game["pgn"], args.username)
        mine = [m for m in analysis.moves if m.color == color]
        user_moves[f"g{i + 1}"] = mine
        grades.update(m.grade for m in mine)
        for m in analysis.moves:
            for theme in set(m.themes) & {"quietMove", "defensiveMove"}:
                quiet_defensive.append((i + 1, theme, m))

    print("\nUser's grades:", dict(grades.most_common()))
    print("\nTop weakness cards (games affected, times):")
    for card in top_weaknesses(user_moves):
        print(f"  {card.theme:16} {card.games:2} of {len(results)} games, {card.times} times")
        for game_id, m in pick_examples(card):
            note = (
                refutation_note(m.refutation_facts, m.color, m.color) if m.refutation_facts else "-"
            )
            print(
                f"      {game_id} {m.move_number}{'.' if m.color == 'white' else '…'} {m.san}"
                f" ({m.grade}, -{m.loss:.0f}): {' '.join(m.refutation_line or [])} | {note}"
            )
    print("\nMissed tactics (times):", [(c.theme, c.times) for c in missed_tactics(user_moves)])

    print(f"\n'quiet move' / 'defensive move' moments ({len(quiet_defensive)}):")
    for game_no, theme, m in quiet_defensive[:12]:
        print(
            f"  g{game_no} {theme:13} {m.color:5} {m.san:7} grade={m.grade:10} "
            f"line: {' '.join(m.refutation_line or [])}  fen_after={m.fen_after}"
        )

    print("\n'great' and 'brilliant' moves (the user's):")
    shown_great = 0
    for game_id, moves in user_moves.items():
        for m in moves:
            if m.grade in ("great", "brilliant") and shown_great < 25:
                shown_great += 1
                print(
                    f"  {game_id} {m.move_number}{'.' if m.color == 'white' else '…'} {m.san:7} "
                    f"{m.grade:9} gap={m.second_gap} before={m.win_before:.0f}%"
                )

    print("\nSample notes (the user's errors, worded for the user and for the opponent):")
    shown = 0
    for game_id, moves in user_moves.items():
        for m in moves:
            if m.refutation_facts and shown < 6:
                shown += 1
                why = refutation_note(m.refutation_facts, m.color, m.color)
                print(f"  {game_id} {m.san:6} {m.grade:10} why: {why}")
                other = "black" if m.color == "white" else "white"
                print(
                    f"  {'':16} as opponent: {refutation_note(m.refutation_facts, m.color, other)}"
                )
                if m.better_facts:
                    print(f"  {'':16} better: {better_note(m.better_facts, m.color, m.color)}")


if __name__ == "__main__":
    main()

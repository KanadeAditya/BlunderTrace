"""Stockfish timing + quality test for BlunderTrace (design research, not app code).

Question: can we grade everything in ONE pass (MultiPV 2: errors + "great" moves),
or does that cost much more than the plain bulk pass (MultiPV 1)?

- Fetches a player's 20 most recent games from chess.com (public API, no key).
- Analyses every position of every game with several engine settings, each
  Stockfish single-threaded (one worker = one core), fresh engine per game+setting.
- Compares each setting against a deep reference (MultiPV 2 @ 1M nodes):
  errors found (Lichess win% thresholds from PLAN.md 4.2) and "great" moves.

Needs Stockfish on PATH (macOS: `brew install stockfish`). From pre_build_research/:
      uv run python engine_timing/timing_test.py fetch <username>     (downloads 20 games)
      uv run python -u engine_timing/timing_test.py run <username>    (analysis, progress, summary)
      uv run python engine_timing/timing_test.py summary <username>   (re-print the table)
games_<username>.json / results_<username>.json are local only (gitignored).
"""

from __future__ import annotations

import io
import json
import math
import re
import sys
import time
import urllib.request
from multiprocessing import Pool
from pathlib import Path

import chess
import chess.engine
import chess.pgn

HERE = Path(__file__).parent
UA = "BlunderTrace-dev-timing-test"
TIME_CLASSES = ["rapid", "blitz"]     # rapid first; blitz only if not enough rapid games
N_GAMES = 20
MAX_MONTHS = 24                       # how far back to look for games
PROCESSES = 4                         # one Stockfish per core; 12 made the laptop hot (see README)

CONFIGS = {                           # name: (multipv, nodes)
    "mpv1_100k": (1, 100_000),        # plain bulk pass (errors only)
    "mpv2_100k": (2, 100_000),        # one pass, same budget
    "mpv2_200k": (2, 200_000),        # one pass, double budget
    "mpv1_50k": (1, 50_000),          # cheaper bulk pass
    "ref_mpv2_1m": (2, 1_000_000),    # deep reference
}


def games_file(user: str) -> Path:
    return HERE / f"games_{user}.json"


def results_file(user: str) -> Path:
    return HERE / f"results_{user}.json"


# ---------- fetching ----------
def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(user: str) -> None:
    archives = get_json(f"https://api.chess.com/pub/player/{user.lower()}/games/archives")["archives"]
    months = [get_json(u) for u in reversed(archives[-MAX_MONTHS:])]   # newest first, one at a time
    for tc in TIME_CLASSES:
        picked = [
            {"url": g["url"], "pgn": g["pgn"], "time_class": tc}
            for month in months
            for g in reversed(month["games"])
            if g.get("rules") == "chess" and g.get("time_class") == tc and g.get("pgn")
        ][:N_GAMES]
        if len(picked) == N_GAMES:
            games_file(user).write_text(json.dumps({"player": user, "time_class": tc, "games": picked}))
            describe(user)
            return
        print(f"only {len(picked)} {tc} games in the last {len(months)} months")
    sys.exit("not enough games found")


def describe(user: str) -> None:
    d = json.loads(games_file(user).read_text())
    dates, elos, tcs = [], [], set()
    for g in d["games"]:
        p = g["pgn"]
        dates.append(re.search(r'\[Date "([^"]+)"', p).group(1))
        elos += [int(re.search(rf'\[{c}Elo "(\d+)"', p).group(1)) for c in ("White", "Black")]
        tcs.add(re.search(r'\[TimeControl "([^"]+)"', p).group(1))
    print(f"{len(d['games'])} {d['time_class']} games of {d['player']}, {min(dates)} to {max(dates)}, "
          f"ratings {min(elos)}-{max(elos)} (avg {sum(elos) // len(elos)}), time controls {sorted(tcs)}")


# ---------- analysis ----------
CAP = 1000


def white_cp(score: chess.engine.PovScore) -> int:
    s = score.white()
    if s.is_mate():
        return CAP if s.mate() > 0 else -CAP
    return max(-CAP, min(CAP, s.score()))


def win(cp_for_mover: int) -> float:
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp_for_mover)) - 1)


def analyse_task(args: tuple[str, int, str]) -> dict:
    user, game_idx, cfg = args
    multipv, nodes = CONFIGS[cfg]
    pgn = json.loads(games_file(user).read_text())["games"][game_idx]["pgn"]
    game = chess.pgn.read_game(io.StringIO(pgn))
    board = game.board()
    moves = list(game.mainline_moves())

    engine = chess.engine.SimpleEngine.popen_uci("stockfish")
    engine.configure({"Threads": 1, "Hash": 64})
    engine.ping()                                   # net loaded before timing starts

    positions = []
    t_total = 0.0
    for i in range(len(moves) + 1):
        if board.is_game_over():
            if board.is_checkmate():
                cp = -CAP if board.turn == chess.WHITE else CAP
            else:
                cp = 0
            positions.append({"cp": cp, "best": None, "second_cp": None})
        else:
            t0 = time.perf_counter()
            infos = engine.analyse(board, chess.engine.Limit(nodes=nodes), multipv=multipv)
            t_total += time.perf_counter() - t0
            if isinstance(infos, dict):
                infos = [infos]
            best = infos[0]
            second = infos[1] if len(infos) > 1 else None
            positions.append({
                "cp": white_cp(best["score"]),
                "best": best["pv"][0].uci() if best.get("pv") else None,
                "second_cp": white_cp(second["score"]) if second else None,
            })
        if i < len(moves):
            board.push(moves[i])
    engine.quit()
    return {"game": game_idx, "cfg": cfg, "seconds": t_total,
            "played": [m.uci() for m in moves], "positions": positions,
            "white_to_move_first": game.board().turn == chess.WHITE}


def grade_game(res: dict) -> list[dict]:
    """Per move: error grade (None/inaccuracy/mistake/blunder) and great flag (None if unknown)."""
    out = []
    pos = res["positions"]
    white_moves = res["white_to_move_first"]
    for i, played in enumerate(res["played"]):
        mover_white = white_moves if i % 2 == 0 else not white_moves
        sign = 1 if mover_white else -1
        before = win(sign * pos[i]["cp"])
        after = win(sign * pos[i + 1]["cp"])
        loss = before - after
        grade = "blunder" if loss >= 15 else "mistake" if loss >= 10 else "inaccuracy" if loss >= 5 else None
        great = None
        if pos[i]["best"] is not None and CONFIGS[res["cfg"]][0] == 2:
            if pos[i]["second_cp"] is None:
                great = False                       # only one legal move: forced, not "great"
            else:
                gap = win(sign * pos[i]["cp"]) - win(sign * pos[i]["second_cp"])
                great = played == pos[i]["best"] and gap >= 10
        out.append({"grade": grade, "great": great, "best": played == pos[i]["best"]})
    return out


def run(user: str) -> None:
    games = json.loads(games_file(user).read_text())
    n = len(games["games"])
    tasks = [(user, g, c) for c in CONFIGS for g in range(n)]
    print(f"{len(tasks)} jobs ({n} games x {len(CONFIGS)} settings) on {PROCESSES} cores, "
          f"one Stockfish per core\n", flush=True)
    t0 = time.perf_counter()
    results = []
    with Pool(PROCESSES) as pool:
        for r in pool.imap_unordered(analyse_task, tasks, chunksize=1):
            results.append(r)
            elapsed = time.perf_counter() - t0
            print(f"[{len(results):>3}/{len(tasks)}  {elapsed/60:4.1f} min]  game {r['game']+1:>2}/{n}  "
                  f"{r['cfg']:<12} {len(r['played']):>3} moves  {r['seconds']:6.1f} s", flush=True)
    wall = time.perf_counter() - t0
    results_file(user).write_text(json.dumps(results))
    summarise(user, wall)


def summarise(user: str, wall: float | None = None) -> None:
    results = json.loads(results_file(user).read_text())
    games = json.loads(games_file(user).read_text())
    by = {(r["game"], r["cfg"]): r for r in results}
    n = len(games["games"])
    plies = [len(by[(g, "ref_mpv2_1m")]["played"]) for g in range(n)]
    print()
    describe(user)
    print(f"avg {sum(plies)/n:.0f} moves per game (both sides counted), {sum(plies)+n} positions total")
    if wall:
        print(f"total wall time for the whole test: {wall/60:.1f} min on {PROCESSES} processes")

    ref = {g: grade_game(by[(g, "ref_mpv2_1m")]) for g in range(n)}
    ref_err = {(g, i) for g in range(n) for i, m in enumerate(ref[g]) if m["grade"]}
    ref_blun = {(g, i) for g in range(n) for i, m in enumerate(ref[g]) if m["grade"] == "blunder"}
    ref_great = {(g, i) for g in range(n) for i, m in enumerate(ref[g]) if m["great"]}
    print(f"reference finds {len(ref_err)} errors ({len(ref_blun)} blunders) and {len(ref_great)} great moves\n")

    print(f"{'setting':<13}{'s/game':>8}{'20-game report, 1 core':>24}{'errors found':>14}"
          f"{'blunders flagged':>18}{'false blunders':>16}{'same grade':>12}{'great found':>13}{'false great':>13}")
    for cfg in CONFIGS:
        per_game = sum(by[(g, cfg)]["seconds"] for g in range(n)) / n
        graded = {g: grade_game(by[(g, cfg)]) for g in range(n)}
        err = {(g, i) for g in range(n) for i, m in enumerate(graded[g]) if m["grade"]}
        blun_flagged = sum(1 for (g, i) in ref_blun if graded[g][i]["grade"])        # any error grade
        false_blun = sum(1 for g in range(n) for i, m in enumerate(graded[g])
                         if m["grade"] == "blunder" and not ref[g][i]["grade"])
        same = sum(1 for (g, i) in ref_err if graded[g][i]["grade"] == ref[g][i]["grade"])
        if CONFIGS[cfg][0] == 2:
            great = {(g, i) for g in range(n) for i, m in enumerate(graded[g]) if m["great"]}
            gf, gx = f"{len(great & ref_great)}/{len(ref_great)}", f"{len(great - ref_great)}"
        else:
            gf, gx = "n/a", "n/a"
        print(f"{cfg:<13}{per_game:>8.1f}{per_game*20/60:>21.1f} min"
              f"{len(err & ref_err):>9}/{len(ref_err):<4}{blun_flagged:>13}/{len(ref_blun):<4}"
              f"{false_blun:>16}{same/max(len(ref_err), 1)*100:>11.0f}%{gf:>13}{gx:>13}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("fetch", "run", "summary"):
        sys.exit("usage: timing_test.py fetch|run|summary <chess.com username>")
    {"fetch": fetch, "run": run, "summary": summarise}[sys.argv[1]](sys.argv[2])

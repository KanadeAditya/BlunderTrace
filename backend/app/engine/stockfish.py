"""One Stockfish process: "analyse this position" -> its two best lines, with scores.

Stockfish is a separate program (C++) that we start once and talk to over stdin/stdout, like
`child_process.spawn('stockfish')` in Node. Waiting for its answer is just waiting, so the async
engine API lets the worker's event loop keep sending heartbeats meanwhile.

Settings that make results repeatable: 1 thread, a fixed number of positions searched per move
(nodes, not time), a fixed hash size, and the hash cleared at the start of every game.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import chess
import chess.engine

log = logging.getLogger(__name__)

EXPECTED_VERSION = "Stockfish 19"


@dataclass
class Line:
    """One of the engine's best lines, scored from White's point of view."""

    cp: int | None
    mate: int | None
    pv: list[str]  # UCI moves


@dataclass
class Position:
    lines: list[Line] = field(default_factory=list)  # best first; empty when the game is over


class EngineCrashed(Exception):
    """Stockfish died twice in a row on one position. A temporary error: the job is retried."""


class Stockfish:
    def __init__(
        self, path: str = "stockfish", nodes: int = 100_000, hash_mb: int = 64, multipv: int = 2
    ) -> None:
        self.path, self.nodes, self.hash_mb, self.multipv = path, nodes, hash_mb, multipv
        self.version = "not started"
        self._engine: chess.engine.UciProtocol | None = None

    async def start(self) -> None:
        try:
            _, self._engine = await chess.engine.popen_uci(self.path)
        except FileNotFoundError:
            raise RuntimeError(f"Stockfish not found at {self.path!r} (STOCKFISH_PATH)") from None
        await self._engine.configure({"Threads": 1, "Hash": self.hash_mb})
        self.version = self._engine.id.get("name", "unknown")
        if not self.version.startswith(EXPECTED_VERSION):
            log.warning(
                "unexpected Stockfish version; results may differ",
                extra={"found": self.version, "expected": EXPECTED_VERSION},
            )
        log.info("Stockfish started", extra={"version": self.version, "nodes": self.nodes})

    async def stop(self) -> None:
        if self._engine is not None:
            try:
                await self._engine.quit()
            except chess.engine.EngineTerminatedError:
                pass
            self._engine = None

    async def _restart(self) -> None:
        await self.stop()
        await self.start()

    async def _analyse(self, board: chess.Board, game: object) -> Position:
        assert self._engine is not None, "call start() first"
        infos = await self._engine.analyse(
            board,
            chess.engine.Limit(nodes=self.nodes),
            multipv=self.multipv,
            # A new `game` object means a new game: python-chess sends "ucinewgame" (clear hash).
            game=game,
            info=chess.engine.INFO_SCORE | chess.engine.INFO_PV,
        )
        lines = []
        for info in infos:
            score, pv = info.get("score"), info.get("pv")
            if score is None or not pv:
                continue
            white = score.white()
            lines.append(Line(cp=white.score(), mate=white.mate(), pv=[m.uci() for m in pv]))
        return Position(lines)

    async def evaluate(self, board: chess.Board, game: object) -> Position:
        if board.is_game_over():
            return Position()
        try:
            return await self._analyse(board, game)
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError):
            log.warning("Stockfish stopped responding; restarting it", exc_info=True)
            await self._restart()
            try:
                return await self._analyse(board, object())
            except (chess.engine.EngineTerminatedError, chess.engine.EngineError) as exc:
                raise EngineCrashed(str(exc)) from exc

    async def evaluate_game(
        self,
        start_fen: str,
        moves_uci: list[str],
        on_position: Callable[[int, Position], Awaitable[None]] | None = None,
    ) -> list[Position]:
        """Every position of a game, from the start to after the last move (moves + 1 results)."""
        game = object()  # fresh per call, so every game (and every retry) starts with a clear hash
        board = chess.Board(start_fen)
        results: list[Position] = []
        for i in range(len(moves_uci) + 1):
            results.append(await self.evaluate(board, game))
            if on_position is not None:
                await on_position(i, results[-1])
            if i < len(moves_uci):
                board.push_uci(moves_uci[i])
        return results


_engine: Stockfish | None = None


async def start_engine(path: str, nodes: int, hash_mb: int) -> Stockfish:
    """Start this worker's one Stockfish (kept running for every game it analyses)."""
    global _engine
    if _engine is None:
        _engine = Stockfish(path=path, nodes=nodes, hash_mb=hash_mb)
        await _engine.start()
    return _engine


def get_engine() -> Stockfish:
    if _engine is None:
        raise RuntimeError("Stockfish is not started (start_engine() runs when a worker starts)")
    return _engine


async def stop_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.stop()
        _engine = None

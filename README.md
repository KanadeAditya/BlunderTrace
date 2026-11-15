# BlunderTrace

> 🚧 **Work in progress.** The research phase is done; the product build is starting.

BlunderTrace is an AI chess coach. It analyses a player's recent games, finds the mistakes they
**keep repeating**, and explains each top issue in plain English, with **cited chess theory** and
the better move.

## How it will work
1. **Find mistakes:** a chess engine (Stockfish) analyses each game and flags the moves that lost
   the most, with the better move and the opponent's winning reply.
2. **Name them:** code labels each mistake with a known type (allowed a fork, left a piece hanging,
   weak back rank…).
3. **Find patterns:** count mistake types across games to get the player's top recurring weaknesses.
4. **Explain them:** retrieve chess theory about each weakness from a corpus (Wikipedia, Wikibooks,
   classic books, Lichess studies) and have an LLM write a grounded explanation with citations.
   Every move it mentions is checked against the engine's lines.
5. **Ask box:** follow-up questions answered from the same corpus.

**Stack:** Python, FastAPI, LangChain/LangGraph, PostgreSQL + pgvector, python-chess, Stockfish,
gpt-4o-mini (Claude Haiku fallback), Docker.

## Research before the build
Before writing the product, we tested whether text embeddings can link chess positions to teaching
text. They can't: embeddings match wording, not chess meaning. Asking about the **chess idea** works
well, though. The full report, data and reproducible test harness are in
[`pre_build_research/`](pre_build_research/README.md).

## Status
- [x] Retrieval feasibility research + corpus (2,425 rows from 5 sources)
- [ ] Mistake detection and labelling (Stockfish + python-chess)
- [ ] Retrieval service (pgvector + full-text search, RRF)
- [ ] API, explanations, Ask box
- [ ] Docker, monitoring, evaluation

Built with AI assistance (Claude).

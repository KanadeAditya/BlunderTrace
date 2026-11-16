# BlunderTrace

> 🚧 **Work in progress.** Research and planning are done; the build has started.

BlunderTrace is an AI chess coach. It analyses a player's recent games, finds the mistakes they
**keep repeating**, and explains each top issue in plain English, with **cited chess theory** and
the better move.

## How it will work
1. **Find mistakes:** Stockfish analyses each game and grades every move (blunder, mistake,
   inaccuracy, miss, …), with the better move and the opponent's winning reply.
2. **Name them:** each mistake is labelled with a known tactical theme (fork, pin, hanging piece, …).
3. **Find patterns:** themes are counted across games to find the player's top recurring weaknesses.
4. **Explain them:** chess theory about each weakness is retrieved from a corpus (Wikipedia,
   Wikibooks, classic books, Lichess studies) and an LLM writes a grounded explanation with
   citations. Every move it mentions is checked against the engine's lines.
5. **Replay games:** a read-only game view with graded moves, an evaluation bar, and animated
   "better move" / "why it's bad" lines.

**Stack:** Vue 3 + TypeScript (frontend) · Python, FastAPI, LangChain/LangGraph (backend) ·
PostgreSQL + pgvector · python-chess · Stockfish · gpt-4o-mini (Claude Haiku fallback) · Docker.

## Repository
```
frontend/             Vue 3 + Vite + TypeScript app
backend/              FastAPI API + analysis worker (Python, uv)
docker-compose.yml    local stack (database for now)
docs/                 PLAN.md (product plan) · API.md (API contract)
pre_build_research/   retrieval feasibility research, corpus and test harness
```

## Running locally (current state)
Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js 20+.
```bash
cp .env.example .env                  # then fill in the keys you need
docker compose up -d db               # Postgres + pgvector

cd backend && uv run uvicorn app.main:app --reload        # API on http://localhost:8000/health
cd frontend && npm install && npm run dev                 # app on http://localhost:5173
```
Tests: `cd backend && uv run pytest`.

## Research before the build
Before writing the product, we tested whether text embeddings can link chess positions to teaching
text. They can't: embeddings match wording, not chess meaning. Asking about the **chess idea** works
well, though. The full report, data and reproducible test harness are in
[`pre_build_research/`](pre_build_research/README.md).

## Status
- [x] Retrieval feasibility research + corpus (2,425 rows from 5 sources)
- [x] Product plan and API contract ([`docs/`](docs/PLAN.md))
- [x] Project setup (frontend, backend, database)
- [ ] Frontend (design, then screens on sample data)
- [ ] Backend: analysis (Stockfish, grading, theme tagging)
- [ ] RAG: retrieval and grounded explanations
- [ ] Production hardening, deployment

## License
[AGPL-3.0](LICENSE). Theme tagging uses code from
[lichess-puzzler](https://github.com/ornicar/lichess-puzzler) (AGPL-3.0).

Built with AI assistance (Claude).

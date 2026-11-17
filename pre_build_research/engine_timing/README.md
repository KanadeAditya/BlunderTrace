# Engine timing test: one pass or two?

**Question.** The plan had two engine passes. A bulk pass, run when the report is made, finds the errors. A deeper pass, run when a game is first opened, finds "great" and "brilliant" moves using MultiPV 2. Can we do everything in one pass instead, and how many nodes per position do we need?

**Decision (backend design, low-level 4).** Use **one pass, MultiPV 2, 100,000 nodes per position**, with the node count set in config. This removes the second pass, the "grading pending" state and the re-polling on the game page.

## Method

The script is `timing_test.py`; see its docstring for how to run it.

- Machine and engine: Stockfish 19 on an Apple M5 Pro.
- One single-threaded Stockfish runs per core (one worker = one core), with `Hash` 64 MB.
- Each game and setting gets a fresh engine. The hash carries over between positions within a game, as it would in a real worker.
- Every position of every game is analysed at each setting, and the results are compared against a deep reference: MultiPV 2 at 1M nodes.
- Grades use the PLAN.md 4.2 rules: Lichess win% loss of 5, 10 and 15 points for inaccuracy, mistake and blunder.
  - The mate rules are simplified: mate scores are capped at ±1000 cp.
  - "Great" means the played move was the best move, and the second-best move was at least 10 win% points worse.
- Errors are counted for both players.

| Setting | MultiPV | Nodes per position | Meaning |
|---|---|---|---|
| `mpv1_50k` | 1 | 50,000 | errors only, cheap |
| `mpv1_100k` | 1 | 100,000 | errors only (the old bulk pass) |
| `mpv2_100k` | 2 | 100,000 | **everything in one pass** |
| `mpv2_200k` | 2 | 200,000 | one pass, double budget |
| `ref_mpv2_1m` | 2 | 1,000,000 | reference |

## Results

### Club level: 20 rapid games (10+0), both players rated 900–1039

- The games average 61 plies; 1,245 positions in total.
- The reference finds 244 errors (111 blunders) and 89 great moves.

| Setting | s / game (1 core) | 20-game report, 1 core | Errors found | Blunders flagged* | False blunders | Same grade | Great found | False great |
|---|---|---|---|---|---|---|---|---|
| mpv1_50k | 6.4 | 2.1 min | 228 / 244 | 110 / 111 | 0 | 70% | – | – |
| mpv1_100k | 10.5 | 3.5 min | 232 / 244 | 111 / 111 | 0 | 77% | – | – |
| **mpv2_100k** | **11.1** | **3.7 min** | **231 / 244** | **111 / 111** | **0** | **79%** | **82 / 89** | **10** |
| mpv2_200k | 23.8 | 7.9 min | 231 / 244 | 111 / 111 | 0 | 77% | 85 / 89 | 9 |
| ref_mpv2_1m | 121.1 | 40.4 min | 244 / 244 | 111 / 111 | 0 | 100% | 89 / 89 | 0 |

### Strong level: 20 blitz games (3+0) of a public IM account (GothamChess), both players rated 2676–2916

- The games average 90 plies; 1,823 positions in total.
- The reference finds 305 errors (107 blunders) and 163 great moves.

| Setting | s / game (1 core) | 20-game report, 1 core | Errors found | Blunders flagged* | False blunders | Great found |
|---|---|---|---|---|---|---|
| mpv1_50k | 9.8 | 3.3 min | 245 / 305 | 105 / 107 | 0 | – |
| mpv1_100k | 17.8 | 5.9 min | 257 / 305 | 107 / 107 | 0 | – |
| **mpv2_100k** | **18.6** | **6.2 min** | **261 / 305** | **105 / 107** | **0** | **145 / 163** |
| mpv2_200k | 37.6 | 12.5 min | 263 / 305 | 107 / 107 | 0 | 143 / 163 |
| ref_mpv2_1m | 188.3 | 62.8 min | 305 / 305 | 107 / 107 | 0 | 163 / 163 |

\* "Blunders flagged" counts the reference's blunders that the setting marked as *any* error. A miss here is usually a borderline blunder graded as a mistake. "False blunders" counts moves the setting called a blunder where the reference sees no error at all.

## Findings

1. **One pass is almost free.** With a fixed node budget, MultiPV 2 shares the same search between two lines. That cost only 4–6% more time than MultiPV 1, and in these games it was no less accurate. It also found 89–92% of the reference's great moves.
2. **200k nodes is not worth it.** It takes twice the time for 0–2 more errors.
3. **50k nodes is the small-server option.** It takes about half the time and still flags almost every blunder, but it agrees less often on the exact grade and misses more of the small errors.
4. **Club games are easier and shorter than strong games.**
   - They are easier: 95% of the reference's errors were found and every blunder was flagged, against 86% for the IM games. Club mistakes are larger and clearer.
   - They are shorter: about 11 s per game against about 19 s.
5. **Expected report time for 20 club games at mpv2_100k:**

   | Workers | Time |
   |---|---|
   | 1 | ~3.7 min |
   | 2 | ~1.9 min |
   | 4 | ~55 s |
   | 8 | ~28 s |

   These times exclude downloading the games and the LLM step.
6. **Memory: each Stockfish 19 process uses about 360 MB**, whether the hash is 16 MB or 64 MB. Most of that is its built-in neural network. Size worker memory with this in mind.

## Caveats

- These are two sets of 20 games, so the percentages are indicative, not precise.
- "Reference" means a deeper Stockfish, not ground truth.
- Running 12 engines at once for 6–9 minutes made the laptop hot. The script now uses 4 processes by default.
- Skipping known opening moves was not tested; it might save a further 10–20%.

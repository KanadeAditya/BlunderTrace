# Retrieval test summary

AUTOMATIC SCORE: hit@5 = share of queries with >=1 top-5 result mentioning the theme (keyword list in retrieval_test.py)

```
variant           full query  short query
A_raw                1/45   2%    12/45  27%
B_template           4/45   9%     5/45  11%
B2_describe          6/45  13%     8/45  18%
C_concepts          11/45  24%    12/45  27%
D_mix                6/45  13%    14/45  31%
D_mix_no_themes      6/45  13%    14/45  31%

Per theme (D_mix, full query) — hits out of 5:
  fork               0/5
  pin                1/5
  skewer             0/5
  discoveredAttack   0/5
  hangingPiece       3/5
  backRankMate       2/5
  trappedPiece       0/5
  exposedKing        0/5
  advancedPawn       0/5

Which sources fill the top 5 in D_mix (full / short query):
  query        lichess_study 225
  query_short  lichess_study 124, gutenberg 97, wikipedia 4
```

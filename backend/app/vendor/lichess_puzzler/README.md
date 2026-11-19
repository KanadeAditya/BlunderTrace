# Vendored: lichess-puzzler tagger

- **Source:** https://github.com/ornicar/lichess-puzzler/tree/8e24b6d5e2b9618e41581a327926e4ac67c610a2/tagger
- **Files:** `cook.py`, `util.py`, `model.py` (and the project's `LICENSE`, AGPL-3.0).
- **Change:** the imports in `cook.py` were made package-relative (`from .model import ...`,
  `from . import util`, `from .util import ...`) so the files work inside this package. Nothing
  else was changed.
- **Not vendored:** `tagger.py` (needs MongoDB), `zugzwang.py` (needs an engine; zugzwang is not
  one of our themes).
- **Verified:** Lichess's own tests from `test.py` run against this copy in
  `backend/tests/test_lichess_tagger.py`.

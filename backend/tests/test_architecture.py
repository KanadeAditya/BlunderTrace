"""The folder rules (docs/BACKEND.md section 4), checked on every test run.

`lint-imports` reads the contracts in pyproject.toml and follows every import in `app/`. If a file
breaks a rule, this test fails with a message such as "app.engine is not allowed to import app.db".
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_import_rules_hold():
    lint_imports = Path(sys.executable).parent / "lint-imports"
    result = subprocess.run([str(lint_imports)], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr

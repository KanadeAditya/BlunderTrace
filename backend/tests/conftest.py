"""Shared test setup. pytest loads this file before any test, like a Jest `setupFiles` entry.

Environment variables beat `.env`, so setting them here means tests never use the real database or
real API keys: any accidental AI call would fail to authenticate instead of costing money.
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = (
    "postgresql://blundertrace:blundertrace@localhost:5432/blundertrace_test"
)
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["OPENAI_API_KEY"] = "test-key-not-real"

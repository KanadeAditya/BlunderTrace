import pytest
from pydantic import ValidationError

from app.config import Settings

URL = "postgresql://u:p@localhost:5432/db"


def make(**values) -> Settings:
    # _env_file=None: only what the test passes (plus the env vars from conftest) counts.
    return Settings(_env_file=None, **values)


def test_defaults_match_the_design():
    s = make(database_url=URL)
    assert (s.workers, s.engine_nodes, s.engine_hash_mb) == (2, 100_000, 64)
    assert (s.report_reuse_minutes, s.max_active_reports) == (10, 20)
    assert (s.main_model, s.fallback_model) == ("claude-haiku-5-5", "gpt-6-luna")
    assert s.stockfish_path == "stockfish"


def test_sqlalchemy_style_url_is_accepted_and_normalised():
    s = make(database_url="postgresql+psycopg://u:p@localhost:5432/db")
    assert s.database_url == URL


def test_non_postgres_url_is_rejected():
    with pytest.raises(ValidationError, match="postgresql://"):
        make(database_url="mysql://u:p@localhost/db")


@pytest.mark.parametrize(
    "field,value", [("engine_nodes", 5), ("workers", 0), ("max_active_reports", 0)]
)
def test_out_of_range_numbers_are_rejected(field, value):
    with pytest.raises(ValidationError):
        make(database_url=URL, **{field: value})


def test_api_keys_are_hidden_when_printed():
    s = make(database_url=URL, openai_api_key="sk-secret")
    assert "sk-secret" not in repr(s)
    assert s.openai_api_key.get_secret_value() == "sk-secret"


def test_a_settings_error_never_prints_values():
    # A bad setting next to a real-looking key: the error must name the field, not echo the key.
    with pytest.raises(ValidationError) as error:
        make(database_url=URL, anthropic_api_key="sk-ant-SECRET-123", engine_nodes="lots")
    assert "engine_nodes" in str(error.value)
    assert "SECRET" not in str(error.value)
    assert "lots" not in str(error.value)


def test_empty_env_values_count_as_not_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert make(database_url=URL).anthropic_api_key is None

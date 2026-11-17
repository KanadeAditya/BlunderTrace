import json
import logging

from app.logs import bind, current_context
from app.logs.setup import JsonFormatter


def format_record(msg: str, **extra) -> dict:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, msg, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter("api").format(record))


def test_a_log_line_is_one_json_object():
    line = format_record("hello")
    assert line["msg"] == "hello"
    assert line["level"] == "INFO"
    assert line["service"] == "api"
    assert line["ts"].endswith("+00:00")


def test_extra_fields_become_their_own_keys():
    line = format_record("request", status=200, duration_ms=3.2)
    assert (line["status"], line["duration_ms"]) == (200, 3.2)


def test_bound_fields_appear_and_disappear():
    with bind(request_id="r1", report_id="r_abc"):
        line = format_record("inside")
        assert (line["request_id"], line["report_id"]) == ("r1", "r_abc")
    assert "request_id" not in format_record("outside")
    assert current_context() == {}


def test_nested_binds_add_up():
    with bind(report_id="r_abc"), bind(game_id="g_1"):
        assert current_context() == {"report_id": "r_abc", "game_id": "g_1"}

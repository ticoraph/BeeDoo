import logging

from beedoo.logs import MasqueCles


def test_api_keys_are_masked():
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "échec avec %s", ("sk-proj-abcdef123456",), None)
    assert MasqueCles().filter(record)
    assert record.getMessage() == "échec avec [clé masquée]"


def test_normal_message_untouched():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "état : veille -> écoute", None, None)
    MasqueCles().filter(record)
    assert record.getMessage() == "état : veille -> écoute"

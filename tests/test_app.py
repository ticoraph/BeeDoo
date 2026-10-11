import pytest

pytest.importorskip("reachy_mini")


def test_app_class_is_importable():
    from beedoo.main import Beedoo

    assert Beedoo.__name__ == "Beedoo"

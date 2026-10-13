"""Server copy: only 1 is singular; 0 and many are plural."""
from wichita_ais_copy import type_breakdown_phrase


def test_others_singular_and_plural() -> None:
    one = type_breakdown_phrase({"a": 5, "b": 4, "c": 3, "d": 1})
    assert one.endswith("and 1 other")
    many = type_breakdown_phrase({"a": 5, "b": 4, "c": 3, "d": 1, "e": 1})
    assert many.endswith("and 2 others")

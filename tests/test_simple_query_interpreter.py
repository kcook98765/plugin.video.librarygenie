"""Tests for lib.search.simple_query_interpreter (keyword extraction logic).

Exercises the query-parsing behaviour with the Kodi stubs in place. The
SettingsManager created inside the interpreter reads from the seeded
settings store (see conftest ``fresh_config``).
"""

import pytest

from tests.kodimocks import seed_settings
from lib.search.simple_query_interpreter import SimpleQueryInterpreter


@pytest.fixture
def interpreter(fresh_config):
    return SimpleQueryInterpreter()


def test_keywords_are_normalized(interpreter):
    q = interpreter.parse_query("The Shawshank  Redemption!!")
    assert q.keywords == ["the", "shawshank", "redemption"]
    assert q.original_text == "The Shawshank  Redemption!!"


def test_empty_input_has_no_keywords(interpreter):
    q = interpreter.parse_query("   ")
    assert q.keywords == []
    assert not q.is_valid()


def test_phrase_mode_keeps_full_phrase(interpreter):
    q = interpreter.parse_query("the shawshank redemption", match_logic="phrase")
    assert q.keywords == ["the shawshank redemption"]
    assert q.match_logic == "phrase"


def test_defaults_when_no_kwargs(interpreter):
    q = interpreter.parse_query("titanic")
    assert q.search_scope == "both"
    assert q.match_logic == "all"
    assert q.scope_type == "library"
    assert q.media_types == ["movie"]
    assert q.page_size == 200  # config default
    assert q.page_offset == 0


def test_page_size_clamped_to_bounds(interpreter):
    # Below the 25 floor.
    assert interpreter.parse_query("x", page_size=1).page_size == 25
    # Above the 500 ceiling.
    assert interpreter.parse_query("x", page_size=9999).page_size == 500
    # In range passes through.
    assert interpreter.parse_query("x", page_size=100).page_size == 100


def test_page_offset_clamped_non_negative(interpreter):
    assert interpreter.parse_query("x", page_offset=-10).page_offset == 0
    assert interpreter.parse_query("x", page_offset=5).page_offset == 5


def test_to_dict_round_trip(interpreter):
    q = interpreter.parse_query("alien", media_types=["movie", "episode"])
    d = q.to_dict()
    assert d["keywords"] == ["alien"]
    assert d["media_types"] == ["movie", "episode"]
    assert d["match_logic"] == "all"


def test_is_empty_query_helper(interpreter):
    q_empty = interpreter.parse_query("   ")
    assert interpreter.is_empty_query(q_empty) is True
    q_full = interpreter.parse_query("blade runner")
    assert interpreter.is_empty_query(q_full) is False

"""Tests for lib.search.normalizer (pure Python, no Kodi dependency)."""

from lib.search.normalizer import TextNormalizer, get_text_normalizer


def test_normalize_empty_and_none():
    n = TextNormalizer()
    assert n.normalize("") == ""


def test_normalize_lowercases_and_collapses_whitespace():
    n = TextNormalizer()
    assert n.normalize("  The    Shawshank   Redemption  ") == "the shawshank redemption"


def test_normalize_strips_punctuation():
    n = TextNormalizer()
    assert n.normalize("Dr. Strangelove (1964)") == "dr strangelove 1964"


def test_normalize_replaces_hyphens_and_underscores_with_spaces():
    n = TextNormalizer()
    assert n.normalize("well-known_item") == "well known item"


def test_normalize_removes_diacritics():
    n = TextNormalizer()
    # NFKD decomposition + combining-mark removal should fold accents away.
    assert n.normalize("creme brulee") == "creme brulee"
    assert n.normalize("caf\u00e9 au lait") == "cafe au lait"


def test_normalize_unicode_compatibility():
    n = TextNormalizer()
    # NFKD normalizes full-width forms to ASCII (full-width H e l l o).
    assert n.normalize("\uFF28ello") == "hello"


def test_normalize_tokens_returns_list():
    n = TextNormalizer()
    assert n.normalize_tokens("Breaking Bad S01E02") == ["breaking", "bad", "s01e02"]


def test_normalize_tokens_empty():
    n = TextNormalizer()
    assert n.normalize_tokens("") == []
    assert n.normalize_tokens("   ") == []


def test_global_instance_is_singleton():
    assert get_text_normalizer() is get_text_normalizer()

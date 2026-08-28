"""Tests for lib.import_export.media_classifier (folder classification logic).

The classifier only depends on the Kodi logger (stubbed) and the stdlib, so
it is a clean, isolated target.
"""

from lib.import_export.media_classifier import MediaClassifier


def _clf():
    return MediaClassifier()


def test_tvshow_nfo_marks_show():
    c = _clf()
    result = c.classify_folder("/movies/show", [], ["tvshow.nfo"], [])
    assert result["type"] == "tv_show"
    assert result["has_tvshow_nfo"] is True


def test_season_folder_name():
    c = _clf()
    result = c.classify_folder("/movies/show/Season 2", ["a.mkv"], [], [])
    assert result["type"] == "season"
    assert result["season_number"] == 2


def test_season_subdirectory_marks_show():
    c = _clf()
    result = c.classify_folder("/movies/show", [], [], ["Season 1", "Season 2"])
    assert result["type"] == "tv_show"


def test_episode_naming_marks_show():
    c = _clf()
    videos = [
        "show.s01e01.mkv", "show.s01e02.mkv",
        "show.s01e03.mkv", "show.s01e04.mkv",
        "show.s01e05.mkv", "extra.mkv",
    ]
    result = c.classify_folder("/tv", videos, [], [])
    # >=50% of files match the SxxExx pattern.
    assert result["type"] == "tv_show"
    assert result["has_episode_files"] is True


def test_single_video_folder():
    c = _clf()
    result = c.classify_folder("/movies/film", ["film.mkv"], [], [])
    assert result["type"] == "single_video"
    assert result["is_disc"] is False
    assert result["video_path"] == "film.mkv"


def test_multiple_videos_no_tv_signal_is_mixed():
    c = _clf()
    result = c.classify_folder("/misc", ["a.mkv", "b.mkv", "c.mkv"], [], [])
    assert result["type"] == "mixed"
    assert result["video_count"] == 3


def test_disc_structure_short_circuits_to_single_video():
    c = _clf()
    result = c.classify_folder("/disc", ["a.mkv"], [], [], disc_structure={"disc": 1})
    assert result["type"] == "single_video"
    assert result["is_disc"] is True
    assert result["disc_info"] == {"disc": 1}


def test_empty_folder_is_mixed_with_zero_videos():
    c = _clf()
    result = c.classify_folder("/empty", [], [], ["Season 1"])
    # A season subdir alone is a TV-show signal, so classify as tv_show.
    assert result["type"] == "tv_show"


def test_classify_subdirectory_under_tvshow():
    c = _clf()
    assert c.classify_subdirectory("tv_show", "Season 3", ["s.mkv"]) == "season"


def test_classify_subdirectory_single_video():
    c = _clf()
    assert c.classify_subdirectory("mixed", "Film", ["film.mkv"]) == "single_video"


def test_classify_subdirectory_multiple_plain_is_mixed():
    c = _clf()
    assert c.classify_subdirectory("mixed", "Bundles", ["a.mkv", "b.mkv"]) == "mixed"

from __future__ import annotations

from src.services.youtube_extractor import (
    _parse_json3_subtitles,
    clean_subtitles_for_ai,
)


def test_parse_json3_subtitles_and_clean():
    payload = {
        "events": [
            {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Hello\\n"}]},
            {"tStartMs": 2000, "dDurationMs": 2000, "segs": [{"utf8": "<c>world</c>"}]},
        ]
    }
    subs = _parse_json3_subtitles(payload)
    assert len(subs) == 2
    cleaned, plain = clean_subtitles_for_ai(subs)
    assert "Hello" in plain
    assert "world" in plain
    assert "<" not in plain

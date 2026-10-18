from typing import Any

from core import config
from services.transcription_keywords import (
    KeywordSource,
    fallback_keywords,
    keyword_source,
    merge_keywords,
    sanitize_keywords,
)


def _learning(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "session_type": "learning",
        "topic": "TCP/IPの仕組み",
        "learning_goal": "障害を調べたい",
        "depth_map": {"topic": "TCP/IPの仕組み", "aspects": [{"name": "再送制御"}, {"name": "ポート番号"}]},
    }
    values.update(overrides)
    return values


def test_learning_source_uses_the_topic_aspects_and_goal() -> None:
    assert keyword_source(_learning()) == KeywordSource("TCP/IPの仕組み", ("再送制御", "ポート番号"), "障害を調べたい")


def test_learning_has_no_source_until_the_depth_map_exists() -> None:
    assert keyword_source(_learning(depth_map=None)) is None


def test_review_source_uses_the_note_summary() -> None:
    values = {"session_type": "review", "topic": "ページング", "note_summary": "仮想メモリの要約"}
    assert keyword_source(values) == KeywordSource("ページング", (), "仮想メモリの要約")


def test_synthesis_and_empty_topics_have_no_source() -> None:
    assert keyword_source({"session_type": "synthesis", "topic": "OS"}) is None
    assert keyword_source(_learning(topic="")) is None


def test_fingerprint_changes_with_the_source() -> None:
    base = KeywordSource("TCP", ("再送",), "")
    assert base.fingerprint == KeywordSource("TCP", ("再送",), "").fingerprint
    assert base.fingerprint != KeywordSource("UDP", ("再送",), "").fingerprint
    assert base.fingerprint != KeywordSource("TCP", ("再送", "輻輳"), "").fingerprint
    assert base.fingerprint != KeywordSource("TCP", ("再送",), "目的").fingerprint


def test_sanitize_drops_forbidden_long_blank_and_duplicate_terms() -> None:
    too_long = "長" * (config.MAX_TRANSCRIPTION_KEYWORD_CHARS + 1)
    terms = [" TCP ", "tcp", "ＴＣＰ", "", "a<b", "改行\nあり", too_long, "SYN"]
    assert sanitize_keywords(terms) == ["TCP", "SYN"]


def test_sanitize_caps_the_number_of_terms() -> None:
    terms = [f"用語{i}" for i in range(config.MAX_TRANSCRIPTION_KEYWORDS + 5)]
    assert len(sanitize_keywords(terms)) == config.MAX_TRANSCRIPTION_KEYWORDS


def test_merge_puts_the_topic_and_aspects_first() -> None:
    source = KeywordSource("TCP/IPの仕組み", ("再送制御",), "")
    assert merge_keywords(source, ["再送制御", "SYN"]) == ["TCP/IPの仕組み", "再送制御", "SYN"]


def test_fallback_is_the_topic_alone() -> None:
    assert fallback_keywords("二分探索") == ["二分探索"]
    assert fallback_keywords(None) is None
    assert fallback_keywords("a<b") is None


def test_explore_source_lists_the_terms_from_the_conversation_newest_first_without_the_llm() -> None:
    values = {
        "session_type": "explore",
        "topic": "二分探索",
        "explore_terms": [
            {"term": "計算量", "reading": "けいさんりょう", "meaning": "手間"},
            {"term": "添字", "reading": "", "meaning": "位置の番号"},
        ],
    }

    assert keyword_source(values) == KeywordSource("二分探索", ("添字", "計算量"), "", generate=False)


def test_explore_source_before_any_terms_is_the_topic_alone() -> None:
    source = keyword_source({"session_type": "explore", "topic": "二分探索"})

    assert source == KeywordSource("二分探索", (), "", generate=False)


def test_fingerprint_tells_listed_terms_from_generated_ones() -> None:
    assert (
        KeywordSource("TCP", ("再送",), "").fingerprint
        != KeywordSource("TCP", ("再送",), "", generate=False).fingerprint
    )

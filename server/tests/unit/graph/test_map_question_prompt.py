import pytest
from langchain_core.messages import HumanMessage

from graph.depth_map import build_depth_map
from graph.output_schemas import DepthMapAspectDraft, MapDialogueTurnAnalysis
from graph.prompts import map_question, question
from graph.prompts.map_question import build_map_question_prompt
from graph.prompts.question import PROMPT_FINGERPRINT, build_question_prompt
from graph.state import DepthMapState

_PLAN_FIELDS = {"learning_goal": "未指定", "focus_aspects": "未指定"}


def _depth_map() -> DepthMapState:
    return build_depth_map(
        "システムコール",
        [
            DepthMapAspectDraft(
                name="システムコールの定義",
                is_core=True,
                defined_question="定義できるか",
                reasoned_question="なぜカーネル経由なのか",
                applied_question="strace でどう調べるか",
            )
        ],
    )


class TestBuildMapQuestionPrompt:
    def test_dialogue_intent_injects_the_aspect_core_question(self) -> None:
        depth_map = _depth_map()
        aspect_id = depth_map["aspects"][0]["id"]
        analysis = MapDialogueTurnAnalysis(
            observations=[],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id=aspect_id,
        )
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="ユーザー: システムコールとは…",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
            depth_map=depth_map,
            map_covered=[{"aspect_id": aspect_id, "reached_stage": "defined"}],
            turn_analysis=analysis,
        )
        assert intent == "dialogue"
        assert "なぜカーネル経由なのか" in prompt
        assert "日常的な具体例だけで終わらせない" in prompt

    def test_wrap_up_overrides_the_mode_section(self) -> None:
        depth_map = _depth_map()
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="なるほど、分かりました")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=None,
            wrap_up=True,
        )
        assert intent == "dialogue"
        assert "区切りの提案" in prompt

    def test_missing_analysis_falls_back_to_self_judged_mode(self) -> None:
        depth_map = _depth_map()
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="なるほど")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=None,
        )
        assert intent == "dialogue"
        assert "応答モードの判定原則" in prompt

    def test_unknown_intent_uses_the_hint_mode(self) -> None:
        depth_map = _depth_map()
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="わかりません")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=None,
        )
        assert intent == "unknown_a"
        assert "全般的な不知" in prompt

    def test_no_map_covered_entry_shows_defined_question(self) -> None:
        depth_map = _depth_map()
        aspect_id = depth_map["aspects"][0]["id"]
        analysis = MapDialogueTurnAnalysis(
            observations=[],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id=aspect_id,
        )
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="ユーザー: システムコール…",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="ユーザー発話")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=analysis,
        )
        assert intent == "dialogue"
        assert "定義できるか" in prompt
        assert "この観点の核心（地図より）" in prompt

    def test_selected_aspect_not_in_depth_map_no_hint(self) -> None:
        depth_map = _depth_map()
        analysis = MapDialogueTurnAnalysis(
            observations=[],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id="nonexistent-aspect",
        )
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="ユーザー発話")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=analysis,
        )
        assert intent == "dialogue"
        assert "この観点の核心（地図より）" not in prompt


_NEW_GOAL = "なぜ必要か・どう成り立つか（必要性・仕組み）まで述べられる"


def _analysis(aspect_id: str, mode: str) -> MapDialogueTurnAnalysis:
    return MapDialogueTurnAnalysis(
        observations=[],
        has_misconception=False,
        response_mode=mode,  # type: ignore[arg-type]
        selected_aspect_id=aspect_id,
    )


def _dialogue_prompt(mode: str) -> str:
    depth_map = _depth_map()
    aspect_id = depth_map["aspects"][0]["id"]
    prompt, _ = build_map_question_prompt(
        topic="システムコール",
        recent_messages="",
        plan_fields=_PLAN_FIELDS,
        messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
        depth_map=depth_map,
        map_covered=[{"aspect_id": aspect_id, "reached_stage": "defined"}],
        turn_analysis=_analysis(aspect_id, mode),
    )
    return prompt


class TestMapPromptSteersToWhyAndHow:
    def test_deepen_turn_has_the_new_goal_and_no_shallow_instructions(self) -> None:
        prompt = _dialogue_prompt("deepen")
        assert _NEW_GOAL in prompt
        assert "具体例または動作原理" not in prompt
        assert "日常生活で、この取り出し順が役に立つ場面を1つ挙げてもらえますか" not in prompt
        assert "なぜカーネル経由なのか" in prompt
        assert "必要性・仕組みを問う" in prompt

    def test_reinforce_and_expand_reuse_the_legacy_bodies(self) -> None:
        assert "モード A" in _dialogue_prompt("reinforce")
        assert "モード B" in _dialogue_prompt("expand")

    def test_map_wrap_up_speaks_of_why_and_mechanism(self) -> None:
        prompt, _ = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="なるほど")],
            depth_map=_depth_map(),
            map_covered=[],
            turn_analysis=None,
            wrap_up=True,
        )
        assert "なぜ・仕組みまで説明できた観点" in prompt
        assert "具体例・動作原理以上" not in prompt

    def test_legacy_prompt_is_untouched(self) -> None:
        prompt, _ = build_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
        )
        assert "具体例または動作原理" in prompt

    def test_legacy_prompt_fingerprint_is_unchanged(self) -> None:
        # eval の regression が capture 済みレコードと同一プロンプトかを判定する値
        assert PROMPT_FINGERPRINT == "141b88d49022"


class TestMapPromptFingerprint:
    def test_is_stable_and_distinct_from_the_legacy_fingerprint(self) -> None:
        assert map_question._map_prompt_fingerprint() == map_question._map_prompt_fingerprint()
        assert map_question.MAP_PROMPT_FINGERPRINT == map_question._map_prompt_fingerprint()
        assert len(map_question.MAP_PROMPT_FINGERPRINT) == 12
        assert map_question.MAP_PROMPT_FINGERPRINT != PROMPT_FINGERPRINT

    @pytest.mark.parametrize(
        "name",
        [
            "MAP_QUESTION_PROMPT_BASE",
            "MAP_TURN_ANALYSIS_PROMPT",
            "_MAP_WRAP_UP",
            "_MAP_DEEPEN_SECTION",
            "_MAP_DEEPEN_EXAMPLE",
        ],
    )
    def test_tracks_map_prompt_text(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setattr(map_question, name, getattr(map_question, name) + "\n追記")
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_the_aspect_list_assembly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setattr(map_question, "_format_aspect_list", lambda depth_map: "変更した一覧")
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_shared_mode_examples(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setitem(question._MODE_EXAMPLES, "reinforce", "変更した応答例")
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_the_fallback_for_an_unknown_aspect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setitem(question._PREDECIDED_MODE_BODIES, "deepen", ("変更した指示",))
        assert map_question._map_prompt_fingerprint() != before

from langchain_core.messages import HumanMessage

from graph.depth_map import build_depth_map
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation, MapDialogueTurnAnalysis
from graph.prompts.map_question import build_map_question_prompt
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
            observations=[MapAspectObservation(aspect_id=aspect_id, reached_stage="defined")],
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
            map_covered=[],
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

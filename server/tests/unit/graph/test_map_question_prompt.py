import pytest
from langchain_core.messages import HumanMessage

from graph import depth_map as depth_map_module
from graph.depth_map import build_depth_map
from graph.output_schemas import DepthMapAspectDraft, MapDialogueTurnAnalysis
from graph.prompts import map_question, map_turn_analysis, question
from graph.prompts.map_question import build_map_question_prompt
from graph.prompts.question import PROMPT_FINGERPRINT, build_question_prompt
from graph.state import DepthMapAspectState, DepthMapState, MapStage

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

    def test_expand_reuses_the_legacy_body(self) -> None:
        assert "モード B" in _dialogue_prompt("expand")

    def test_reinforce_states_the_error_first_without_a_positive_preface(self) -> None:
        prompt = _dialogue_prompt("reinforce")
        assert "応答の最初に、ユーザーの説明のどの部分が誤りかを明示する" in prompt
        assert "説明しようとした取り組みを短く受け止める" not in prompt
        assert "訂正文の一般則にそのまま当てはめるだけで答えが出る問い" in prompt

    def test_reinforce_for_an_aspect_not_on_the_map_also_uses_the_map_body(self) -> None:
        prompt, _ = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
            depth_map=_depth_map(),
            map_covered=[],
            turn_analysis=_analysis("missing", "reinforce"),
        )
        assert "応答の最初に、ユーザーの説明のどの部分が誤りかを明示する" in prompt
        assert "説明しようとした取り組みを短く受け止める" not in prompt

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

    def test_map_base_policy_names_the_error_instead_of_correcting_gently(self) -> None:
        prompt = _dialogue_prompt("deepen")
        assert "優しく訂正する" not in prompt
        assert "「間違いです」）は行わない" not in prompt
        assert "どの部分が誤りかを明示する" in prompt
        assert "誤りのない説明への短い受け止め" in prompt

    def test_dialogue_fallback_without_analysis_also_names_the_error_first(self) -> None:
        prompt, _ = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
            depth_map=_depth_map(),
            map_covered=[],
            turn_analysis=None,
        )
        assert "説明しようとした取り組みを短く受け止める" not in prompt
        assert "応答の最初に、ユーザーの説明のどの部分が誤りかを明示する" in prompt
        assert "訂正文の一般則にそのまま当てはめるだけで答えが出る問い" in prompt
        assert "説明してくれてありがとうございます" not in prompt
        assert "誤りの箇所を最初に明示し、訂正は定義の修正にとどめる" in prompt

    def test_reinforce_overrides_the_apply_to_a_new_example_rules(self) -> None:
        prompt = _dialogue_prompt("reinforce")
        assert (
            "共通ルールの「新しい例への適用で理解を確かめる」「必要な答えを具体的に示してよい」より優先する" in prompt
        )

    def test_reinforce_does_not_ask_for_what_the_correction_already_states(self) -> None:
        assert "どこが違ったか" not in _dialogue_prompt("reinforce")

    @pytest.mark.parametrize("mode", ["reinforce", "deepen"])
    def test_core_rules_override_the_supplement_allowance_but_allow_correcting_the_error(self, mode: str) -> None:
        prompt = _dialogue_prompt(mode)
        assert "共通ルールの「前提の簡潔な補足はよい」より優先する" in prompt
        assert "誤りそのものの訂正は述べてよい" in prompt

    def test_map_base_policy_still_forbids_declaring_the_answer_correct(self) -> None:
        assert "「正解です」" in _dialogue_prompt("deepen")

    def test_legacy_base_policy_is_untouched(self) -> None:
        prompt, _ = build_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
        )
        assert "優しく訂正する" in prompt

    def test_legacy_prompt_fingerprint_is_unchanged(self) -> None:
        # eval の regression が capture 済みレコードと同一プロンプトかを判定する値
        assert PROMPT_FINGERPRINT == "141b88d49022"

    @pytest.mark.parametrize("mode", ["reinforce", "expand", "deepen"])
    def test_core_question_is_framed_as_an_internal_guide(self, mode: str) -> None:
        prompt = _dialogue_prompt(mode)
        assert "応答の中で読み上げたり言い換えて述べたりしない" in prompt
        assert "ユーザーがまだ述べていなければ応答で先に述べない" in prompt
        assert "観点名は内部のラベル" in prompt

    def test_core_rules_are_absent_when_the_aspect_is_not_on_the_map(self) -> None:
        prompt, _ = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
            depth_map=_depth_map(),
            map_covered=[],
            turn_analysis=_analysis("missing", "deepen"),
        )
        assert "応答の中で読み上げたり言い換えて述べたりしない" not in prompt


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
            "_MAP_WRAP_UP",
            "_MAP_DEEPEN_SECTION",
            "_MAP_DEEPEN_EXAMPLE",
            "_MAP_CORE_RULES",
            "_MAP_REINFORCE_SECTION",
            "_MAP_REINFORCE_EXAMPLE",
            "_MAP_MODE_DIALOGUE",
        ],
    )
    def test_tracks_map_prompt_text(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setattr(map_question, name, getattr(map_question, name) + "\n追記")
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_the_turn_analysis_prompt_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setattr(
            map_turn_analysis, "MAP_TURN_ANALYSIS_PROMPT", map_turn_analysis.MAP_TURN_ANALYSIS_PROMPT + "\n追記"
        )
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_the_aspect_list_assembly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setattr(map_turn_analysis, "_format_aspect_list", lambda depth_map: "変更した一覧")
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_shared_mode_examples(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setitem(question._MODE_EXAMPLES, "expand", "変更した応答例")
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_the_fallback_for_an_unknown_aspect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setitem(question._PREDECIDED_MODE_BODIES, "deepen", ("変更した指示",))
        assert map_question._map_prompt_fingerprint() != before

    @pytest.mark.parametrize("stage", ["mentioned", "defined", "reasoned", "applied"])
    def test_tracks_every_stage_label(self, monkeypatch: pytest.MonkeyPatch, stage: MapStage) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setitem(depth_map_module.STAGE_LABELS, stage, "変更した段階名")
        assert map_question._map_prompt_fingerprint() != before

    @pytest.mark.parametrize("stage", ["defined", "reasoned", "applied"])
    def test_tracks_the_question_chosen_for_each_stage(self, monkeypatch: pytest.MonkeyPatch, stage: MapStage) -> None:
        before = map_question._map_prompt_fingerprint()
        original = depth_map_module.question_for

        def changed(aspect: DepthMapAspectState, target: MapStage) -> str:
            text = original(aspect, target)
            return text + "変更" if target == stage else text

        monkeypatch.setattr(map_question, "question_for", changed)
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_the_empty_coverage_placeholder_of_the_turn_analysis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        monkeypatch.setattr(map_turn_analysis, "_EMPTY_COVERAGE_PLACEHOLDER", "（変更）")
        assert map_question._map_prompt_fingerprint() != before

    def test_tracks_how_the_turn_analysis_prompt_is_assembled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = map_question._map_prompt_fingerprint()
        original = map_turn_analysis.build_map_turn_analysis_prompt
        monkeypatch.setattr(
            map_question, "build_map_turn_analysis_prompt", lambda **kwargs: original(**kwargs) + "変更"
        )
        assert map_question._map_prompt_fingerprint() != before


class TestBracesInGeneratedText:
    def _build(self, *, aspect_name: str, question: str, error_summary: str = "") -> str:
        depth_map = build_depth_map(
            "Python",
            [
                DepthMapAspectDraft(
                    name=aspect_name,
                    is_core=True,
                    defined_question=question,
                    reasoned_question=question,
                    applied_question=question,
                )
            ],
        )
        analysis = MapDialogueTurnAnalysis(
            observations=[],
            has_misconception=bool(error_summary),
            error_summary=error_summary,
            response_mode="reinforce" if error_summary else "deepen",
            selected_aspect_id=depth_map["aspects"][0]["id"],
        )
        prompt, _ = build_map_question_prompt(
            topic="Python",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="辞書はキーで値を引く仕組みです")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=analysis,
        )
        return prompt

    def test_braces_in_the_aspect_name_and_core_question_are_kept_verbatim(self) -> None:
        prompt = self._build(aspect_name="f文字列 {name}", question="{count} とは何か")
        assert "{count} とは何か" in prompt
        assert "f文字列 {name}" in prompt

    def test_braces_in_the_error_summary_are_kept_verbatim(self) -> None:
        prompt = self._build(aspect_name="辞書", question="定義できるか", error_summary="{key} を値と混同している")
        assert "{key} を値と混同している" in prompt

    def test_output_matches_the_previous_assembly_for_brace_free_input(self) -> None:
        depth_map = _depth_map()
        aspect_id = depth_map["aspects"][0]["id"]
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=aspect_id
        )
        messages = [HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")]
        prompt, _ = build_map_question_prompt(
            topic="システムコール",
            recent_messages="ユーザー: …",
            plan_fields=_PLAN_FIELDS,
            messages=messages,
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=analysis,
        )
        previous = (
            map_question.MAP_QUESTION_PROMPT_BASE
            + "\n"
            + map_question._build_map_dialogue_section(analysis, depth_map, [])
        ).format(
            topic="システムコール",
            recent_messages="ユーザー: …",
            coverage_section=map_question._build_coverage_section([], depth_map),
            **_PLAN_FIELDS,
        )
        assert prompt == previous

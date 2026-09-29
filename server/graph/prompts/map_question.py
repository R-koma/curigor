"""地図駆動の学習対話の応答生成プロンプト。question.py のモード構造を再利用する。"""

from collections.abc import Sequence
from typing import Any

from graph.depth_map import format_map_coverage, next_stage, question_for
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts.question import (
    MODE_DIALOGUE,
    MODE_HINT,
    MODE_UNKNOWN_A,
    MODE_UNKNOWN_B,
    MODE_UNKNOWN_C,
    MODE_WRAP_UP,
    QUESTION_PROMPT_BASE,
    UserIntent,
    build_mode_section,
    classify_user_intent,
)
from graph.state import DepthMapState, MapAspectProgress, MapStage

_OLD_GOAL = "ユーザーが各観点について「自分の言葉で説明でき、具体例または動作原理まで述べられる」状態を目標とする。"
_NEW_GOAL = (
    "ユーザーが各観点について「自分の言葉で説明でき、なぜ必要か・どう成り立つか（必要性・仕組み）まで述べられる」"
    "状態を目標とする。日常の具体例を1つ挙げられるだけでは到達とみなさない。"
)
_OLD_WRAP_UP_PHRASE = "具体例・動作原理以上まで説明できた観点"

assert _OLD_GOAL in QUESTION_PROMPT_BASE
assert _OLD_WRAP_UP_PHRASE in MODE_WRAP_UP

MAP_QUESTION_PROMPT_BASE = QUESTION_PROMPT_BASE.replace(_OLD_GOAL, _NEW_GOAL)
_MAP_WRAP_UP = MODE_WRAP_UP.replace(_OLD_WRAP_UP_PHRASE, "なぜ・仕組みまで説明できた観点")

_MAP_DEEPEN_SECTION = """\
### モード C: 深掘り / 具体化（選んだ観点の必要性・仕組みを問う時）
選んだ観点について、なぜ必要か・どう成り立っているかを1つだけ問う。
- 「なぜ〜が必要か」「〜が無いと何が困るか」「どう成り立っているか」のいずれかを、下の核心の問いに沿って問う
- 日常の具体例を挙げさせない（目標段階が応用のときを除く）
- 既に述べた内容を、同じ深さで再説明させない
- 質問前に、その質問の答えとなる必要性や仕組みを解説しない

応答長の目安: 1〜3 文。
"""

_MAP_DEEPEN_EXAMPLE = """\
## モード C の応答例（形式を参考にし、例の話題を持ち込まない）
ユーザー: 「キューは先に入れたものを先に取り出す仕組みです」
AI: 「先に入れたものから取り出す、という順番が守られないと、何が困るのでしょうか？」
※ 具体例を挙げさせるのではなく、必要性・仕組みを問う。答えは先に示さない。
"""

_MODE_SECTIONS: dict[UserIntent, str] = {
    "exhausted": MODE_HINT,
    "unknown_a": MODE_UNKNOWN_A,
    "unknown_b": MODE_UNKNOWN_B,
    "unknown_c": MODE_UNKNOWN_C,
}


def _reached_stage(aspect_id: str, map_covered: Sequence[MapAspectProgress]) -> MapStage | None:
    for c in map_covered:
        if c["aspect_id"] == aspect_id:
            return c["reached_stage"]
    return None


def _build_map_dialogue_section(
    analysis: MapDialogueTurnAnalysis, depth_map: DepthMapState, map_covered: Sequence[MapAspectProgress]
) -> str:
    aspect = next((a for a in depth_map["aspects"] if a["id"] == analysis.selected_aspect_id), None)
    if aspect is None:
        return build_mode_section(
            response_mode=analysis.response_mode,
            selected_aspect_label=analysis.selected_aspect_id,
            error_summary=analysis.error_summary,
        )
    target_stage = next_stage(_reached_stage(aspect["id"], map_covered))
    hint = (
        "### この観点の核心（地図より）\n"
        f"{question_for(aspect, target_stage)}\n"
        "この核心に向かって問いを組み立てる。日常的な具体例だけで終わらせない。"
    )
    is_deepen = analysis.response_mode == "deepen"
    return build_mode_section(
        response_mode=analysis.response_mode,
        selected_aspect_label=aspect["name"],
        error_summary=analysis.error_summary,
        extra_hint=hint,
        mode_body=_MAP_DEEPEN_SECTION if is_deepen else None,
        mode_example=_MAP_DEEPEN_EXAMPLE if is_deepen else None,
    )


def _build_coverage_section(map_covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> str:
    lines = format_map_coverage(map_covered, depth_map)
    if not lines:
        return ""
    return (
        "## カバー済み観点と到達度（過去ターン累積）\n"
        f"{lines}\n"
        "上記の観点は記載の段階まで説明済みとして扱い、同じ深さの質問を繰り返さない。\n\n"
    )


def build_map_question_prompt(
    *,
    topic: str,
    recent_messages: str,
    plan_fields: dict[str, str],
    messages: Sequence[Any],
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
    turn_analysis: MapDialogueTurnAnalysis | None,
    wrap_up: bool = False,
) -> tuple[str, UserIntent]:
    intent = classify_user_intent(messages)
    if intent == "dialogue" and wrap_up:
        mode_section = _MAP_WRAP_UP
    elif intent == "dialogue" and turn_analysis is not None:
        mode_section = _build_map_dialogue_section(turn_analysis, depth_map, map_covered)
    elif intent == "dialogue":
        mode_section = MODE_DIALOGUE
    else:
        mode_section = _MODE_SECTIONS[intent]
    template = MAP_QUESTION_PROMPT_BASE + "\n" + mode_section
    prompt = template.format(
        topic=topic,
        recent_messages=recent_messages,
        coverage_section=_build_coverage_section(map_covered, depth_map),
        **plan_fields,
    )
    return prompt, intent

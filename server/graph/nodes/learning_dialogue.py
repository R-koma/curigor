from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.coverage import coverage_progress, merge_coverage
from graph.llm import llm
from graph.multimodal import load_image_blocks
from graph.nodes._shared import recent_messages_block
from graph.nodes._turn_analysis import analyze_dialogue_turn
from graph.output_schemas import DialogueTurnAnalysis
from graph.prompts import build_question_prompt, classify_user_intent, format_learning_plan_fields
from graph.prompts.question import PROMPT_FINGERPRINT, PROMPT_VERSION
from graph.state import CoveredAspect, LearningState, TurnAnalysisRecord
from storage import get_storage


@dataclass(frozen=True)
class TurnPlan:
    """事前分析が決めた、このターンのプロンプトへ注入する値。"""

    covered_aspects: list[CoveredAspect] = field(default_factory=list)
    analysis: DialogueTurnAnalysis | None = None
    wrap_up: bool = False


def _to_record(analysis: DialogueTurnAnalysis | None, wrap_up: bool) -> TurnAnalysisRecord | None:
    """プロンプトに注入された決定内容だけを state 保存用に抜き出す。"""
    if analysis is None:
        return None
    return TurnAnalysisRecord(
        response_mode=analysis.response_mode,
        selected_aspect=analysis.selected_aspect,
        has_misconception=analysis.has_misconception,
        error_summary=analysis.error_summary,
        wrap_up=wrap_up,
    )


def _turn_context(state: LearningState) -> tuple[str, dict[str, str]]:
    recent_messages = recent_messages_block(state)
    plan_fields = format_learning_plan_fields(
        learning_goal=state.get("learning_goal"),
        focus_aspects=state.get("focus_aspects"),
    )
    return recent_messages, plan_fields


async def prepare_turn(state: LearningState) -> TurnPlan:
    """応答生成の前に事前分析を 1 回行い、観点カバレッジと応答モードを決める。

    dialogue intent 以外では分析しない。分析が失敗してもターンは止めず、
    `analysis=None` を返して呼び出し側をモード自己判定のプロンプトへフォールバックさせる。

    観点カバレッジが基準に達し、誤りが無く、未提案なら区切りを提案する（`wrap_up`）。
    """
    recent_messages, plan_fields = _turn_context(state)
    covered_aspects: list[CoveredAspect] = list(state.get("covered_aspects") or [])
    analysis: DialogueTurnAnalysis | None = None
    if classify_user_intent(state["messages"]) == "dialogue":
        analysis = await analyze_dialogue_turn(
            state,
            recent_messages=recent_messages,
            plan_fields=plan_fields,
            covered_aspects=covered_aspects,
        )
        if analysis is not None:
            covered_aspects = merge_coverage(covered_aspects, analysis.observations)
    wrap_up = (
        analysis is not None
        and not analysis.has_misconception
        and not state.get("wrap_up_offered")
        and coverage_progress(covered_aspects, state.get("focus_aspects")).is_complete
    )
    return TurnPlan(covered_aspects=covered_aspects, analysis=analysis, wrap_up=wrap_up)


async def respond(state: LearningState, plan: TurnPlan) -> dict[str, Any]:
    """決定済みの `plan` で質問プロンプトを組み、応答を生成する。

    分析と分けてあるのは、eval が保存済みの決定を注入して応答生成だけを再実行できるようにするため
    （分析の揺れとプロンプト改訂の効果を切り分ける）。
    """
    recent_messages, plan_fields = _turn_context(state)
    question_prompt, intent = build_question_prompt(
        topic=state["topic"],
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        messages=state["messages"],
        covered_aspects=plan.covered_aspects,
        turn_analysis=plan.analysis,
        wrap_up=plan.wrap_up,
    )
    llm_messages: list[BaseMessage] = [SystemMessage(content=question_prompt)]
    if state["messages"]:
        image_blocks = await load_image_blocks(state["messages"][-1], get_storage())
        if image_blocks:
            llm_messages.append(HumanMessage(content=image_blocks))

    response = await llm.ainvoke(
        llm_messages,
        config={
            "metadata": {
                "prompt_version": PROMPT_VERSION,
                "prompt_fingerprint": PROMPT_FINGERPRINT,
                "intent": intent,
                "response_mode": plan.analysis.response_mode if plan.analysis else None,
                "selected_aspect": plan.analysis.selected_aspect if plan.analysis else None,
                "wrap_up": plan.wrap_up,
            }
        },
    )

    return {
        "messages": [response],
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "covered_aspects": plan.covered_aspects,
        "turn_analysis": _to_record(plan.analysis, plan.wrap_up),
        "wrap_up_offered": bool(state.get("wrap_up_offered")) or plan.wrap_up,
    }


async def learning_dialogue(state: LearningState) -> dict[str, Any]:
    """対話継続: ファシリテーターとして説明を促す（評価はしない）。

    決定内容（response_mode / selected_aspect）は state に残す。プロンプトを変える値なので、
    これが無いと会話履歴と state からターンを再現できない（eval の regression 実行で使う）。

    学習セッションはユーザーの明示的な終了操作で完了するため、`should_generate_note` は常に False を返す。
    観点カバレッジが基準に達したターンでは区切り（ノート作成）を提案するが、終了はしない。
    （終了スイッチは api/websocket/chat.py の `_handle_end_session` が外部から立てる）
    """
    return await respond(state, await prepare_turn(state))

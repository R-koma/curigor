"""学習対話ターンの事前分析（カバレッジ観測 + 応答モード決定）。

応答生成の前に軽量モデルを 1 回呼ぶ。失敗しても対話ターン自体は止めず、
None を返して呼び出し側を MODE_DIALOGUE（自己判定）へフォールバックさせる。
"""

import logging
from collections.abc import Sequence

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.output_schemas import DialogueTurnAnalysis
from graph.prompts.turn_analysis import build_turn_analysis_prompt
from graph.state import CoveredAspect, LearningState

logger = logging.getLogger(__name__)


async def analyze_dialogue_turn(
    state: LearningState,
    *,
    recent_messages: str,
    plan_fields: dict[str, str],
    covered_aspects: Sequence[CoveredAspect],
) -> DialogueTurnAnalysis | None:
    prompt = build_turn_analysis_prompt(
        topic=state["topic"],
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        covered_aspects=covered_aspects,
    )
    runnable = llm_structured.with_structured_output(DialogueTurnAnalysis, task="turn-analysis").with_config(
        tags=[INTERNAL_LLM_TAG]
    )
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=prompt)],
            config={"run_name": "turn-analysis"},
        )
    except Exception:
        logger.warning("turn analysis failed; falling back to self-judged dialogue mode", exc_info=True)
        return None
    if not isinstance(result, DialogueTurnAnalysis):
        logger.warning("turn analysis returned unexpected type %s; falling back", type(result).__name__)
        return None
    return _with_mode_from_misconception(result)


def _with_mode_from_misconception(analysis: DialogueTurnAnalysis) -> DialogueTurnAnalysis:
    """誤りを検出したターンのモードを reinforce に揃える。

    プロンプトでも指示しているが、文面だけに任せると深さの判断に引きずられて deepen / expand が
    返る（この分析ステップが元々そう壊れていた）。訂正セクションをプロンプトへ載せる条件は
    `response_mode == "reinforce"` なので、ここがずれると検出できても訂正が指示されない。
    """
    if not analysis.has_misconception or analysis.response_mode == "reinforce":
        return analysis
    logger.warning("turn analysis flagged a misconception but chose %s; forcing reinforce", analysis.response_mode)
    return analysis.model_copy(update={"response_mode": "reinforce"})

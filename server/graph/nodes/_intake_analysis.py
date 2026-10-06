"""聞き取り1ターンの構造化抽出（learning_dialogue の聞き取りフェーズ用）。

失敗しても聞き取りターン自体は止めず、None を返して呼び出し側に今回は抽出できなかった
扱いをさせる（_turn_analysis.py と同じフォールバック方針）。
"""

import logging

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.output_schemas import IntakeExtraction
from graph.prompts.intake import INTAKE_PROMPT_FINGERPRINT, build_intake_extraction_prompt
from graph.state import LearningState

logger = logging.getLogger(__name__)


async def extract_intake(
    state: LearningState, *, recent_messages: str, confirm_topic: bool = False
) -> IntakeExtraction | None:
    prompt = build_intake_extraction_prompt(
        topic=state["topic"],
        purpose=state.get("learning_goal") or "",
        source=state.get("learning_source") or "",
        prior_knowledge=state.get("prior_knowledge") or "",
        recent_messages=recent_messages,
        confirm_topic=confirm_topic,
    )
    runnable = llm_structured.with_structured_output(IntakeExtraction).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke(
            [SystemMessage(content=prompt)],
            config={"run_name": "extract-intake", "metadata": {"prompt_fingerprint": INTAKE_PROMPT_FINGERPRINT}},
        )
    except Exception:
        logger.warning("intake extraction failed", exc_info=True)
        return None
    if not isinstance(result, IntakeExtraction):
        logger.warning("intake extraction returned unexpected type %s", type(result).__name__)
        return None
    return result

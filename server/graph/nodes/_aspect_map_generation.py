import logging
from typing import Any
from uuid import UUID

from langchain_core.messages import BaseMessage, SystemMessage

from graph.llm import llm_structured
from graph.output_schemas import AspectMap
from graph.prompts import GENERATE_ASPECT_MAP_PROMPT

logger = logging.getLogger(__name__)


async def generate_aspect_map(conversation_text: str, note_id: UUID) -> AspectMap | None:
    aspect_llm = llm_structured.with_structured_output(AspectMap, task="generate-aspect-map")
    try:
        result: Any = await aspect_llm.ainvoke(
            [
                SystemMessage(content=GENERATE_ASPECT_MAP_PROMPT),
                {"role": "user", "content": conversation_text},
            ],
            config={"run_name": "generate-aspect-map"},
        )
    except Exception:
        logger.warning("aspect map generation failed for note %s", note_id, exc_info=True)
        return None

    if not isinstance(result, AspectMap):
        logger.warning("aspect map generation returned unexpected type for note %s", note_id)
        return None
    return result


def conversation_text_for_aspect_map(messages: list[BaseMessage]) -> str:
    return "".join(f"{'ユーザー' if m.type == 'human' else 'アシスタント'}: {m.content}\n" for m in messages)

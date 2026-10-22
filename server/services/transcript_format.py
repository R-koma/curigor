import asyncio
import logging
import re
import unicodedata
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from core import config
from graph.llm import llm
from graph.prompts.transcript_format import TRANSCRIPT_FORMAT_PROMPT_FINGERPRINT, build_transcript_format_prompt
from observability.langfuse_tracing import traced_transcript_format

logger = logging.getLogger(__name__)

_IGNORED = re.compile(
    r"[\s。、．，.,!！?？「」『』]"
    r"|(?:えー*っ?と|えー+|うー+ん+|うーん+|んー+|あー+|あの|その|まあ|なんか)ー*"
)
_MIN_KEPT_RATIO = 0.9


class TranscriptFormatError(Exception):
    pass


def _normalize(text: str) -> str:
    return _IGNORED.sub("", unicodedata.normalize("NFKC", text))


def is_deletion_only(before: str, after: str) -> bool:
    original = _normalize(before)
    result = _normalize(after)
    remaining = iter(original)
    if not all(char in remaining for char in result):
        return False
    return len(result) >= _MIN_KEPT_RATIO * len(original)


async def format_transcript(text: str, *, session_id: UUID, user_id: str) -> str:
    prompt = build_transcript_format_prompt(text)
    async with traced_transcript_format(session_id=session_id, user_id=user_id, characters=len(text)) as run:
        invoke_config: RunnableConfig = {
            "run_name": "format-transcript",
            "metadata": {"prompt_fingerprint": TRANSCRIPT_FORMAT_PROMPT_FINGERPRINT},
        }
        if "callbacks" in run.config:
            invoke_config["callbacks"] = run.config["callbacks"]
        try:
            async with asyncio.timeout(config.TRANSCRIPT_FORMAT_TIMEOUT_SECONDS):
                response = await llm.ainvoke([HumanMessage(content=prompt)], invoke_config, task="format-transcript")
        except Exception as exc:
            raise TranscriptFormatError("Transcript formatting failed") from exc
        formatted = response.text.strip()
        if not formatted or not is_deletion_only(text, formatted):
            logger.warning("Formatted transcript rejected: not a deletion-only edit")
            run.set_output({"rejected": True})
            return text
        run.set_output(formatted)
        return formatted

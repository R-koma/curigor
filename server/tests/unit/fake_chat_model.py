from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda

USAGE: Any = {
    "input_tokens": 100,
    "output_tokens": 30,
    "total_tokens": 130,
    "input_token_details": {"cache_read": 40},
    "output_token_details": {"reasoning": 10},
}


class FakeChatModel(BaseChatModel):
    seen_tags: list[list[str]] = []
    fail: bool = False

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._result(run_manager)

    def _result(self, run_manager: CallbackManagerForLLMRun | AsyncCallbackManagerForLLMRun | None) -> ChatResult:
        self.seen_tags.append(list(run_manager.tags) if run_manager else [])
        if self.fail:
            raise RuntimeError("boom")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok", usage_metadata=USAGE))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._result(run_manager)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable[Any, Any]:
        return self | RunnableLambda(lambda message: {"text": message.content})

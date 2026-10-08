from dataclasses import dataclass
from functools import cache
from typing import Any, Literal, cast, get_args

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI

load_dotenv()

Provider = Literal["openai", "anthropic"]

ResponseTask = Literal[
    "learning-kickoff",
    "learning-dialogue",
    "review-start",
    "review-dialogue",
    "synthesis-start",
    "synthesis-dialogue",
]

StructuredTask = Literal[
    "generate-intake-card",
    "extract-intake",
    "generate-depth-map",
    "turn-analysis",
    "map-turn-analysis",
    "review-turn-analysis",
    "estimate-category",
    "suggest-collection",
    "generate-note-content",
    "generate-aspect-map",
    "analyze-dialogue",
    "generate-feedback-scores",
    "revise-note",
    "append-review-addendum",
    "synthesis-insights",
    "generate-collection-synthesis",
]


@dataclass(frozen=True)
class ModelSpec:
    provider: Provider
    model: str
    reasoning_effort: str | None = None
    temperature: float | None = None


_LUNA_RESPONSE = ModelSpec(provider="openai", model="gpt-6-luna", reasoning_effort="none", temperature=0.7)
_LUNA_STRUCTURED = ModelSpec(provider="openai", model="gpt-6-luna", reasoning_effort="none", temperature=0)

RESPONSE_MODELS: dict[ResponseTask, ModelSpec] = dict.fromkeys(get_args(ResponseTask), _LUNA_RESPONSE)
STRUCTURED_MODELS: dict[StructuredTask, ModelSpec] = dict.fromkeys(get_args(StructuredTask), _LUNA_STRUCTURED)


@cache
def build_chat_model(spec: ModelSpec) -> BaseChatModel:
    if spec.provider == "openai":
        return ChatOpenAI(  # type: ignore[call-arg]
            model=spec.model, temperature=spec.temperature, reasoning_effort=spec.reasoning_effort
        )
    return ChatAnthropic(model=spec.model, temperature=spec.temperature, effort=cast(Any, spec.reasoning_effort))


for _spec in {*RESPONSE_MODELS.values(), *STRUCTURED_MODELS.values()}:
    build_chat_model(_spec)


class ResponseLLM:
    async def ainvoke(
        self, input: LanguageModelInput, config: RunnableConfig | None = None, *, task: ResponseTask
    ) -> AIMessage:
        response = await build_chat_model(RESPONSE_MODELS[task]).ainvoke(input, config)
        assert isinstance(response, AIMessage)
        if isinstance(response.content, str):
            return response
        # Anthropic は本文を thinking などのブロックの配列で返す。state とプロンプトの履歴は文字列を前提にする。
        # id を変えると LangGraph の messages ストリームが別のメッセージとして本文をもう一度流す
        return response.model_copy(update={"content": response.text})


class StructuredLLM:
    def with_structured_output(self, schema: type, *, task: StructuredTask) -> Runnable[LanguageModelInput, Any]:
        spec = STRUCTURED_MODELS[task]
        model = build_chat_model(spec)
        if spec.provider == "anthropic":
            # 既定の function_calling はツールの強制指定を使い、Claude の現行モデルは 400 を返す
            return model.with_structured_output(schema, method="json_schema")
        return model.with_structured_output(schema)


llm = ResponseLLM()
llm_structured = StructuredLLM()
llm_judge: ChatAnthropic = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

INTERNAL_LLM_TAG = "internal-llm"

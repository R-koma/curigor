from typing import Annotated, Literal, NotRequired
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from graph.output_schemas import ResponseMode

ReachedDepth = Literal["mentioned", "defined", "exemplified", "applied"]


class CoveredAspect(TypedDict):
    aspect: str
    reached_depth: ReachedDepth


class TurnAnalysisRecord(TypedDict):
    """事前分析のうち、プロンプトに注入された決定内容だけを残す記録。

    `DialogueTurnAnalysis` をそのまま持たず TypedDict に落とすのは、チェックポイントの
    シリアライズ経路を素の dict に揃えるため（`CoveredAspect` と同じ扱い）。
    `observations` は `covered_aspects` へマージ済みなので含めない。
    """

    response_mode: ResponseMode
    selected_aspect: str
    has_misconception: bool
    error_summary: str
    wrap_up: NotRequired[bool]


class LearningState(TypedDict):
    user_id: str
    dialogue_session_id: UUID
    note_id: UUID
    messages: Annotated[list[BaseMessage], add_messages]
    topic: str
    turn_count: int
    should_generate_note: bool
    session_type: str
    note_content: NotRequired[str]
    note_summary: NotRequired[str]
    prior_improvements: NotRequired[str]
    learning_goal: NotRequired[str]
    focus_aspects: NotRequired[list[str]]
    covered_aspects: NotRequired[list[CoveredAspect]]
    turn_analysis: NotRequired[TurnAnalysisRecord | None]
    wrap_up_offered: NotRequired[bool]

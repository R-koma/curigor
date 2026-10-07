from typing import Annotated, Literal, NotRequired
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from graph.output_schemas import MapUserIntent, ResponseMode

ReachedDepth = Literal["mentioned", "defined", "exemplified", "applied"]

MapStage = Literal["mentioned", "defined", "reasoned", "applied"]
"""深さの地図の到達段階。既存 ReachedDepth（mentioned/defined/exemplified/applied）とは独立させる。

exemplified（具体例または動作原理）を reasoned（なぜ・仕組み）に置き換え、
具体例1つで到達扱いになる浅い基準をなくすための地図専用の段階。
"""


class DepthMapAspectState(TypedDict):
    id: str
    name: str
    is_core: bool
    defined_question: str
    reasoned_question: str
    applied_question: str


class DepthMapState(TypedDict):
    topic: str
    aspects: list[DepthMapAspectState]


class MapAspectProgress(TypedDict):
    aspect_id: str
    reached_stage: MapStage


class CoveredAspect(TypedDict):
    aspect: str
    reached_depth: ReachedDepth


class SynthesisConnectionState(TypedDict):
    id: str
    title: str
    explanation: str
    question: str


TopicCorrectionStatus = Literal["asked", "accepted", "declined", "failed"]


class TopicCorrectionRecord(TypedDict):
    previous_topic: str
    new_topic: str
    status: TopicCorrectionStatus


class PendingTopicCorrection(TypedDict):
    new_topic: str


class RelatedNote(TypedDict):
    note_id: str
    topic: str
    summary: str


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
    selected_aspect_id: NotRequired[str]
    topic_correction: NotRequired[TopicCorrectionRecord]
    user_intent: NotRequired[MapUserIntent]
    unknown_streak: NotRequired[int]


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
    review_focus_aspects: NotRequired[list[str]]
    learning_goal: NotRequired[str]
    focus_aspects: NotRequired[list[str]]
    covered_aspects: NotRequired[list[CoveredAspect]]
    turn_analysis: NotRequired[TurnAnalysisRecord | None]
    wrap_up_offered: NotRequired[bool]
    intake_complete: NotRequired[bool]
    intake_turns: NotRequired[int]
    intake_message_count: NotRequired[int]
    learning_source: NotRequired[str]
    prior_knowledge: NotRequired[str]
    depth_map: NotRequired[DepthMapState]
    related_notes: NotRequired[list[RelatedNote]]
    map_covered: NotRequired[list[MapAspectProgress]]
    pending_topic_correction: NotRequired[PendingTopicCorrection | None]
    collection_id: NotRequired[UUID]
    synthesis_notes: NotRequired[str]
    synthesis_connections: NotRequired[list[SynthesisConnectionState]]

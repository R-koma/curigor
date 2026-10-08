from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage

from graph.output_schemas import IntakeCardDraft, IntakeOptionDraft
from graph.state import DepthMapAspectState, DepthMapState, LearningState
from graph.trial import TRIAL_PURPOSE, limit_core_aspects

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": [],
        "topic": "システムコール",
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "learning",
    }
    base.update(overrides)
    return cast(LearningState, base)


def _draft() -> IntakeCardDraft:
    return IntakeCardDraft(
        topic="システムコール",
        purpose_options=[IntakeOptionDraft(label="面接対策"), IntakeOptionDraft(label="基礎を理解したい")],
        source_options=[IntakeOptionDraft(label="書籍"), IntakeOptionDraft(label="授業")],
        inferred_purpose="面接対策",
    )


class TestLearningStart:
    async def test_returns_intake_card_with_normalized_topic(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=_draft())):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state(topic="面接でシステムコールを聞かれるので学びたい"))

        assert result["topic"] == "システムコール"
        assert result["turn_count"] == 1
        assert result["intake_complete"] is False
        assert result["intake_turns"] == 0
        assert result["should_generate_note"] is False
        user_message, ai_message = result["messages"]
        assert user_message.content == "面接でシステムコールを聞かれるので学びたい"
        assert isinstance(ai_message, AIMessage)
        assert "システムコール" in ai_message.content
        card = ai_message.additional_kwargs["intake_card"]
        assert [q["key"] for q in card["questions"]] == ["purpose", "source", "prior_knowledge"]
        assert card["questions"][0]["preselected"] == ["面接対策"]

    async def test_starts_with_fallback_card_when_generation_fails(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=None)):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state())

        assert result["topic"] == "システムコール"
        assert result["intake_complete"] is False
        assert result["messages"][1].additional_kwargs["intake_card"]["questions"]

    async def test_omits_purpose_question_when_api_provided_learning_goal(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=_draft())):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state(learning_goal="面接対策"))

        keys = [q["key"] for q in result["messages"][1].additional_kwargs["intake_card"]["questions"]]
        assert keys == ["source", "prior_knowledge"]


class TestLearningStartWithAmbiguousTopic:
    def _ambiguous_draft(self) -> IntakeCardDraft:
        return IntakeCardDraft(
            topic_is_clear=False,
            topic="この仕組み",
            topic_candidates=[],
            purpose_options=[IntakeOptionDraft(label="面接対策"), IntakeOptionDraft(label="基礎を理解したい")],
            source_options=[IntakeOptionDraft(label="書籍"), IntakeOptionDraft(label="授業")],
        )

    async def test_asks_for_the_topic_and_does_not_state_it_in_the_lead(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=self._ambiguous_draft())):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state(topic="この仕組みを学びたい"))

        ai_message = result["messages"][1]
        keys = [q["key"] for q in ai_message.additional_kwargs["intake_card"]["questions"]]
        assert keys == ["topic", "purpose", "source", "prior_knowledge"]
        assert "この仕組み" not in ai_message.content
        assert result["intake_complete"] is False

    async def test_clear_topic_keeps_the_existing_lead(self) -> None:
        with patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=_draft())):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state())

        assert "システムコールを学ぶんですね" in result["messages"][1].content


def _depth_map() -> DepthMapState:
    def aspect(aspect_id: str, is_core: bool) -> DepthMapAspectState:
        return {
            "id": aspect_id,
            "name": aspect_id,
            "is_core": is_core,
            "defined_question": "",
            "reasoned_question": "",
            "applied_question": "",
        }

    return {"topic": "虹が見える理由", "aspects": [aspect("a", True), aspect("b", True), aspect("c", False)]}


class TestTrialLearningStart:
    async def test_skips_the_intake_card_and_starts_the_map_with_one_core_aspect(self) -> None:
        generate = AsyncMock(return_value=_depth_map())
        draft = AsyncMock()
        with (
            patch("graph.nodes.learning_start.generate_depth_map", generate),
            patch("graph.nodes.learning_start.draft_intake_card", draft),
        ):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state(topic="虹が見える理由", trial=True))

        draft.assert_not_called()
        assert generate.await_args is not None
        assert generate.await_args.kwargs["purpose"] == TRIAL_PURPOSE
        assert result["intake_complete"] is True
        assert result["topic"] == "虹が見える理由"
        assert result["learning_goal"] == TRIAL_PURPOSE
        assert result["intake_message_count"] == 1
        assert result["map_covered"] == []
        assert result["related_notes"] == []
        assert [a["is_core"] for a in result["depth_map"]["aspects"]] == [True, False, False]
        user_message, ai_message = result["messages"]
        assert user_message.content == "虹が見える理由"
        assert "intake_card" not in ai_message.additional_kwargs
        assert ai_message.additional_kwargs["trial_kickoff"] is True
        assert "虹が見える理由" in ai_message.content

    async def test_falls_back_to_the_intake_card_when_the_map_fails(self) -> None:
        with (
            patch("graph.nodes.learning_start.generate_depth_map", AsyncMock(return_value=None)),
            patch("graph.nodes.learning_start.draft_intake_card", AsyncMock(return_value=None)),
        ):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state(topic="虹が見える理由", trial=True))

        assert result["intake_complete"] is False
        assert "intake_card" in result["messages"][1].additional_kwargs


class TestLimitCoreAspects:
    def test_keeps_the_first_core_aspects_and_demotes_the_rest(self) -> None:
        limited = limit_core_aspects(_depth_map(), 1)

        assert [(a["id"], a["is_core"]) for a in limited["aspects"]] == [("a", True), ("b", False), ("c", False)]

    def test_does_not_modify_the_original_map(self) -> None:
        original = _depth_map()
        limit_core_aspects(original, 1)

        assert original["aspects"][1]["is_core"] is True

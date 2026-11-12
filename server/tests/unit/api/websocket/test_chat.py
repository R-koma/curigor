import json
from typing import Any, get_args
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from api.websocket.chat import _progress_from_values, _read_turn_state, _stream_ai_response
from graph.coverage import WRAP_UP_MIN_ASPECTS
from graph.state import MapStage
from schemas.websocket_message import ProgressStage


class _FakeState:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values


class TestReadTurnState:
    async def test_returns_the_state_values(self) -> None:
        graph = MagicMock(aget_state=AsyncMock(return_value=_FakeState({"turn_count": 1})))
        assert await _read_turn_state(graph, {}) == {"turn_count": 1}

    async def test_returns_none_on_failure(self) -> None:
        graph = MagicMock(aget_state=AsyncMock(side_effect=RuntimeError("down")))
        assert await _read_turn_state(graph, {}) is None


class TestProgressFromValues:
    def test_uses_depth_map_progress_when_depth_map_present(self) -> None:
        depth_map = {
            "topic": "t",
            "aspects": [
                {
                    "id": "a",
                    "name": "観点A",
                    "is_core": True,
                    "defined_question": "d",
                    "reasoned_question": "r",
                    "applied_question": "ap",
                }
            ],
        }
        progress = _progress_from_values(
            {"depth_map": depth_map, "map_covered": [{"aspect_id": "a", "reached_stage": "reasoned"}]}
        )
        assert progress is not None
        assert progress.reached_aspects == ["観点A"]
        assert progress.is_complete is True

    def test_falls_back_to_legacy_coverage_without_depth_map(self) -> None:
        progress = _progress_from_values({"covered_aspects": [{"aspect": "前提条件", "reached_depth": "exemplified"}]})
        assert progress is not None
        assert progress.reached_aspects == ["前提条件"]
        assert progress.target_count == WRAP_UP_MIN_ASPECTS
        assert progress.is_complete is False

    def test_empty_state_reports_the_legacy_defaults(self) -> None:
        progress = _progress_from_values({})
        assert progress is not None
        assert progress.reached_aspects == []
        assert progress.target_count == WRAP_UP_MIN_ASPECTS
        assert progress.is_complete is False

    def test_only_core_aspects_count_toward_the_depth_map_target(self) -> None:
        def aspect(aspect_id: str, name: str, *, core: bool) -> dict[str, Any]:
            return {
                "id": aspect_id,
                "name": name,
                "is_core": core,
                "defined_question": "d",
                "reasoned_question": "r",
                "applied_question": "ap",
            }

        depth_map = {
            "topic": "t",
            "aspects": [
                aspect("a", "中核A", core=True),
                aspect("b", "中核B", core=True),
                aspect("c", "周辺C", core=False),
            ],
        }
        covered = [
            {"aspect_id": "a", "reached_stage": "reasoned"},
            {"aspect_id": "c", "reached_stage": "applied"},
        ]
        progress = _progress_from_values({"depth_map": depth_map, "map_covered": covered})
        assert progress is not None
        assert progress.reached_aspects == ["中核A"]
        assert progress.target_count == 2
        assert progress.is_complete is False


def _map_aspect(aspect_id: str, name: str, *, core: bool) -> dict[str, Any]:
    return {
        "id": aspect_id,
        "name": name,
        "is_core": core,
        "defined_question": f"{name}とは何か",
        "reasoned_question": f"なぜ{name}が必要か",
        "applied_question": f"{name}をどう使うか",
    }


class TestProgressAspects:
    def test_lists_core_aspects_first_and_marks_unreached_as_none(self) -> None:
        depth_map = {
            "topic": "t",
            "aspects": [
                _map_aspect("c", "周辺C", core=False),
                _map_aspect("a", "中核A", core=True),
                _map_aspect("b", "中核B", core=True),
            ],
        }
        covered = [
            {"aspect_id": "b", "reached_stage": "defined"},
            {"aspect_id": "c", "reached_stage": "mentioned"},
        ]
        progress = _progress_from_values({"depth_map": depth_map, "map_covered": covered})
        assert progress is not None
        assert [a.model_dump() for a in progress.aspects] == [
            {"name": "中核A", "is_core": True, "reached_stage": None},
            {"name": "中核B", "is_core": True, "reached_stage": "defined"},
            {"name": "周辺C", "is_core": False, "reached_stage": "mentioned"},
        ]

    def test_serialized_progress_carries_no_core_questions_or_ids(self) -> None:
        depth_map = {"topic": "t", "aspects": [_map_aspect("aspect-a", "中核A", core=True)]}
        covered = [{"aspect_id": "aspect-a", "reached_stage": "reasoned"}]
        progress = _progress_from_values({"depth_map": depth_map, "map_covered": covered})
        assert progress is not None
        dumped = progress.model_dump_json()
        for leaked in ("中核Aとは何か", "なぜ中核Aが必要か", "中核Aをどう使うか", "aspect-a", '"id"', "aspect_id"):
            assert leaked not in dumped

    def test_aspects_are_empty_without_depth_map(self) -> None:
        covered = [{"aspect": "前提条件", "reached_depth": "exemplified"}]
        progress = _progress_from_values({"covered_aspects": covered})
        assert progress is not None
        assert progress.aspects == []

    def test_progress_stage_matches_the_graph_map_stage(self) -> None:
        assert get_args(ProgressStage) == get_args(MapStage)


class TestProgressDuringIntake:
    def test_no_progress_while_the_intake_card_is_unanswered(self) -> None:
        assert _progress_from_values({"intake_complete": False}) is None

    def test_progress_is_reported_for_sessions_that_predate_the_intake_flag(self) -> None:
        progress = _progress_from_values({"covered_aspects": [{"aspect": "前提条件", "reached_depth": "exemplified"}]})
        assert progress is not None
        assert progress.reached_aspects == ["前提条件"]

    def test_progress_is_reported_once_intake_is_complete_without_a_map(self) -> None:
        progress = _progress_from_values({"intake_complete": True})
        assert progress is not None
        assert progress.target_count == WRAP_UP_MIN_ASPECTS

    def test_progress_is_reported_once_intake_is_complete_with_a_map(self) -> None:
        depth_map = {"topic": "t", "aspects": [_map_aspect("a", "観点A", core=True)]}
        progress = _progress_from_values({"intake_complete": True, "depth_map": depth_map, "map_covered": []})
        assert progress is not None
        assert [a.name for a in progress.aspects] == ["観点A"]


class TestIntakeSummary:
    def test_carries_the_learning_premise_from_state(self) -> None:
        progress = _progress_from_values(
            {
                "intake_complete": True,
                "learning_goal": "基礎知識を身につける",
                "learning_source": "入門書、公式ドキュメント",
                "prior_knowledge": "初めて学ぶ",
            }
        )
        assert progress is not None
        assert progress.intake is not None
        assert progress.intake.model_dump() == {
            "purpose": "基礎知識を身につける",
            "source": "入門書、公式ドキュメント",
            "prior_knowledge": "初めて学ぶ",
        }

    def test_keeps_answered_fields_and_blanks_the_rest(self) -> None:
        progress = _progress_from_values(
            {"intake_complete": True, "learning_source": " 入門書 ", "prior_knowledge": "  "}
        )
        assert progress is not None
        assert progress.intake is not None
        assert progress.intake.model_dump() == {"purpose": "", "source": "入門書", "prior_knowledge": ""}

    def test_is_none_when_every_field_was_skipped(self) -> None:
        progress = _progress_from_values(
            {"intake_complete": True, "learning_goal": "", "learning_source": "", "prior_knowledge": ""}
        )
        assert progress is not None
        assert progress.intake is None

    def test_is_none_for_sessions_from_before_the_intake(self) -> None:
        progress = _progress_from_values({"covered_aspects": []})
        assert progress is not None
        assert progress.intake is None


class TestPendingQuestions:
    _MAP = {"topic": "T", "aspects": [_map_aspect("a", "A", core=True), _map_aspect("b", "B", core=True)]}

    async def _end(self, values: dict[str, Any]) -> dict[str, Any]:
        graph = MagicMock(aget_state=AsyncMock(return_value=_FakeState(values)))
        graph.astream = MagicMock(return_value=_no_chunks())
        websocket = MagicMock(send_text=AsyncMock())

        await _stream_ai_response(graph, None, {}, websocket, state_config={})

        return dict(json.loads(websocket.send_text.await_args.args[0]))

    async def test_assistant_message_end_carries_pending_questions(self) -> None:
        end = await self._end(
            {
                "dialogue_phase": "free",
                "depth_map": self._MAP,
                "map_covered": [{"aspect_id": "a", "reached_stage": "reasoned"}],
                "messages": [AIMessage(content="声かけ"), HumanMessage(content="説明"), AIMessage(content="受け止め")],
            }
        )

        assert end["type"] == "assistant_message_end"
        assert end["pending_questions"] == 1

    async def test_pending_questions_is_sent_alongside_an_end_confirmation(self) -> None:
        end = await self._end(
            {
                "dialogue_phase": "free",
                "depth_map": self._MAP,
                "end_confirmation": "offered",
                "asked_aspect_ids": ["a"],
                "messages": [HumanMessage(content="説明"), AIMessage(content="質問は以上です")],
            }
        )

        assert end["end_confirmation"] is not None
        assert end["pending_questions"] == 1

    async def test_pending_questions_is_none_for_legacy_values(self) -> None:
        end = await self._end(
            {"depth_map": self._MAP, "messages": [HumanMessage(content="説明"), AIMessage(content="質問")]}
        )

        assert end["pending_questions"] is None


async def _no_chunks() -> Any:
    return
    yield

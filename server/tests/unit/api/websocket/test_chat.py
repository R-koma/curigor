from typing import Any
from unittest.mock import AsyncMock, MagicMock

from api.websocket.chat import _learning_progress
from graph.coverage import WRAP_UP_MIN_ASPECTS


class _FakeState:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values


class TestLearningProgress:
    async def test_uses_depth_map_progress_when_depth_map_present(self) -> None:
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
        graph = MagicMock(
            aget_state=AsyncMock(
                return_value=_FakeState(
                    {"depth_map": depth_map, "map_covered": [{"aspect_id": "a", "reached_stage": "reasoned"}]}
                )
            )
        )
        progress = await _learning_progress(graph, {})
        assert progress is not None
        assert progress.reached_aspects == ["観点A"]
        assert progress.is_complete is True

    async def test_falls_back_to_legacy_coverage_without_depth_map(self) -> None:
        graph = MagicMock(
            aget_state=AsyncMock(
                return_value=_FakeState({"covered_aspects": [{"aspect": "前提条件", "reached_depth": "exemplified"}]})
            )
        )
        progress = await _learning_progress(graph, {})
        assert progress is not None
        assert progress.reached_aspects == ["前提条件"]
        assert progress.target_count == WRAP_UP_MIN_ASPECTS
        assert progress.is_complete is False

    async def test_empty_state_reports_the_legacy_defaults(self) -> None:
        graph = MagicMock(aget_state=AsyncMock(return_value=_FakeState({})))
        progress = await _learning_progress(graph, {})
        assert progress is not None
        assert progress.reached_aspects == []
        assert progress.target_count == WRAP_UP_MIN_ASPECTS
        assert progress.is_complete is False

    async def test_only_core_aspects_count_toward_the_depth_map_target(self) -> None:
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
        graph = MagicMock(
            aget_state=AsyncMock(return_value=_FakeState({"depth_map": depth_map, "map_covered": covered}))
        )
        progress = await _learning_progress(graph, {})
        assert progress is not None
        assert progress.reached_aspects == ["中核A"]
        assert progress.target_count == 2
        assert progress.is_complete is False

    async def test_returns_none_on_failure(self) -> None:
        graph = MagicMock(aget_state=AsyncMock(side_effect=RuntimeError("down")))
        assert await _learning_progress(graph, {}) is None

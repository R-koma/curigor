from typing import Any
from unittest.mock import AsyncMock, MagicMock

from api.websocket.chat import _learning_progress


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

    async def test_returns_none_on_failure(self) -> None:
        graph = MagicMock(aget_state=AsyncMock(side_effect=RuntimeError("down")))
        assert await _learning_progress(graph, {}) is None

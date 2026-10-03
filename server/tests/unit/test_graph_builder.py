from typing import cast

from graph.builder import (
    route_after_learning_dialogue,
    route_after_review_dialogue,
    route_after_synthesis_dialogue,
    route_entry,
)
from graph.state import LearningState


class TestRouteEntry:
    def test_routes_to_review_start_for_review(self) -> None:
        state = cast(LearningState, {"session_type": "review"})
        assert route_entry(state) == "review_start"

    def test_routes_to_learning_start_for_learning(self) -> None:
        state = cast(LearningState, {"session_type": "learning"})
        assert route_entry(state) == "learning_start"

    def test_defaults_to_learning_start_when_session_type_missing(self) -> None:
        state = cast(LearningState, {})
        assert route_entry(state) == "learning_start"


class TestRouteAfterLearningDialogue:
    def test_loops_when_should_not_generate_note(self) -> None:
        state = cast(LearningState, {"should_generate_note": False})
        assert route_after_learning_dialogue(state) == "learning_dialogue"

    def test_proceeds_to_generate_note_when_ended(self) -> None:
        state = cast(LearningState, {"should_generate_note": True})
        assert route_after_learning_dialogue(state) == "generate_note"


class TestRouteAfterReviewDialogue:
    def test_loops_when_should_not_generate_note(self) -> None:
        state = cast(LearningState, {"should_generate_note": False})
        assert route_after_review_dialogue(state) == "review_dialogue"

    def test_proceeds_to_update_note_and_feedback_when_ended(self) -> None:
        state = cast(LearningState, {"should_generate_note": True})
        assert route_after_review_dialogue(state) == "update_note_and_feedback"


class TestRouteEntryForSynthesis:
    def test_routes_to_synthesis_start(self) -> None:
        state = cast(LearningState, {"session_type": "synthesis"})
        assert route_entry(state) == "synthesis_start"


class TestRouteAfterSynthesisDialogue:
    def test_loops_until_ended(self) -> None:
        state = cast(LearningState, {"should_generate_note": False})
        assert route_after_synthesis_dialogue(state) == "synthesis_dialogue"

    def test_finishes_when_ended(self) -> None:
        state = cast(LearningState, {"should_generate_note": True})
        assert route_after_synthesis_dialogue(state) == "finish_synthesis"

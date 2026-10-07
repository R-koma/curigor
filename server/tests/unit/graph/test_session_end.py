from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from graph.session_end import end_confirmation_after, has_learner_content

_MAP = {"aspects": [{"id": "a1", "name": "定義", "is_core": True}]}


def _learning(**values: Any) -> dict[str, Any]:
    return {"session_type": "learning", **values}


class TestHasLearnerContent:
    def test_map_route_with_a_defined_aspect_has_content(self) -> None:
        values = _learning(depth_map=_MAP, map_covered=[{"aspect_id": "a1", "reached_stage": "defined"}])
        assert has_learner_content(values) is True

    def test_map_route_with_only_mentioned_aspects_has_no_content(self) -> None:
        values = _learning(depth_map=_MAP, map_covered=[{"aspect_id": "a1", "reached_stage": "mentioned"}])
        assert has_learner_content(values) is False

    def test_intake_in_progress_has_no_content(self) -> None:
        assert has_learner_content(_learning(intake_complete=False)) is False

    def test_legacy_route_reads_covered_aspects(self) -> None:
        assert has_learner_content(_learning(covered_aspects=[{"aspect": "x", "reached_depth": "exemplified"}]))
        assert not has_learner_content(_learning(covered_aspects=[{"aspect": "x", "reached_depth": "mentioned"}]))

    def test_review_uses_review_answered(self) -> None:
        assert has_learner_content({"session_type": "review", "review_answered": True}) is True
        assert has_learner_content({"session_type": "review", "review_answered": False}) is False

    def test_review_started_before_the_flag_counts_replies_after_the_seed(self) -> None:
        seed = [HumanMessage(content="二分探索"), AIMessage(content="覚えていることは？")]
        assert has_learner_content({"session_type": "review", "messages": seed}) is False
        replied = [*seed, HumanMessage(content="半分に絞ります")]
        assert has_learner_content({"session_type": "review", "messages": replied}) is True

    def test_synthesis_always_has_content(self) -> None:
        assert has_learner_content({"session_type": "synthesis"}) is True


class TestEndConfirmationAfter:
    def test_first_wish_to_end_is_offered(self) -> None:
        assert end_confirmation_after(None, wants_to_end=True, offer=False) == "offered"

    def test_wish_to_end_after_an_offer_is_confirmed(self) -> None:
        assert end_confirmation_after("offered", wants_to_end=True, offer=False) == "confirmed"

    def test_wrap_up_offers_without_a_wish(self) -> None:
        assert end_confirmation_after(None, wants_to_end=False, offer=True) == "offered"

    def test_anything_else_clears_the_offer(self) -> None:
        assert end_confirmation_after("offered", wants_to_end=False, offer=False) is None

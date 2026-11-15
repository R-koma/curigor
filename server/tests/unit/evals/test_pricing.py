import pytest

from evals import pricing
from evals.pricing import Price
from graph.llm import RESPONSE_MODELS, STRUCTURED_MODELS


def test_estimate_cost_prices_cached_input_separately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pricing, "PRICE_PER_MTOK", {"m": Price(input=2.0, cached_input=0.5, output=10.0)})

    cost = pricing.estimate_cost("m-2026", input_tokens=1_000_000, cached_input_tokens=400_000, output_tokens=100_000)

    assert cost == pytest.approx(0.6 * 2.0 + 0.4 * 0.5 + 0.1 * 10.0)


def test_unknown_model_has_no_cost() -> None:
    assert pricing.estimate_cost("no-such-model", input_tokens=1, output_tokens=1) is None


def test_longer_prefix_wins() -> None:
    assert pricing.price_for("claude-opus-5-5-x") is pricing.PRICE_PER_MTOK["claude-opus-5-5"]
    assert pricing.price_for("claude-sonnet-5-5") is pricing.PRICE_PER_MTOK["claude-sonnet-5-5"]


def test_app_models_are_priced() -> None:
    for spec in {*RESPONSE_MODELS.values(), *STRUCTURED_MODELS.values()}:
        assert pricing.price_for(spec.model) is not None

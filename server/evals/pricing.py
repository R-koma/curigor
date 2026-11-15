from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    """USD / 100 万トークン。"""

    input: float
    cached_input: float
    output: float


# 2026-11-15 に Anthropic と OpenAI の公式の料金ページで確認（OpenAI は Standard・短い文脈）。
# 前方一致で引くので長い名前を先に置く。Haiku 5.5 はプロンプト 100K トークン以下の料金
PRICE_PER_MTOK: dict[str, Price] = {
    "claude-haiku-5-5": Price(0.10, 0.01, 0.50),
    "claude-haiku-4-5": Price(1.0, 0.10, 5.0),
    "claude-sonnet-5-5": Price(2.0, 0.10, 10.0),
    "claude-sonnet-5": Price(2.0, 0.20, 10.0),
    "claude-opus-5-5": Price(4.0, 0.20, 20.0),
    "claude-opus-5": Price(5.0, 0.50, 25.0),
    "gpt-6-luna": Price(0.10, 0.01, 0.50),
    "gpt-6-astra": Price(10.0, 1.0, 50.0),
    "gpt-6-sol": Price(2.0, 0.20, 10.0),
    "gpt-6.1-sol": Price(2.0, 0.10, 10.0),
    "gpt-6.1-terra": Price(1.0, 0.05, 5.0),
}


def price_for(model: str) -> Price | None:
    for prefix, price in PRICE_PER_MTOK.items():
        if model.startswith(prefix):
            return price
    return None


def estimate_cost(model: str, *, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float | None:
    """`input_tokens` はキャッシュ分を含む。推論のトークンは `output_tokens` に含まれる。"""
    price = price_for(model)
    if price is None:
        return None
    uncached = input_tokens - cached_input_tokens
    total = uncached * price.input + cached_input_tokens * price.cached_input + output_tokens * price.output
    return total / 1_000_000

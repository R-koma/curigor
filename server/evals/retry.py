# openai / anthropic の両 SDK が同名で持つ、再試行してよい一時的なエラーの型名。
# langchain-openai は SDK の例外を別名のサブクラス（OpenAITimeoutError など）で包み直すので、親クラスの名前も見る
_TRANSIENT_ERROR_TYPES = frozenset({"APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError"})
# エラーメッセージに現れる課金枯渇の目印。再試行しても直らないので実行全体を止める
_QUOTA_EXHAUSTED_MARKERS = ("insufficient_quota", "credit balance is too low", "exceeded your current quota")


class QuotaExhausted(RuntimeError):
    """API の課金上限・クレジット枯渇。再試行では直らないため、呼び出し元は実行全体を止める。"""


def is_transient(exc: Exception) -> bool:
    return any(cls.__name__ in _TRANSIENT_ERROR_TYPES for cls in type(exc).__mro__)


def is_quota_exhausted(exc: Exception) -> bool:
    text = str(exc)
    return any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS)

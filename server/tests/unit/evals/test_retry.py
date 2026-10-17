import pytest

from evals.retry import is_transient


def _error(name: str, base: type[Exception] = Exception) -> Exception:
    error_type: type[Exception] = type(name, (base,), {})
    return error_type("boom")


@pytest.mark.parametrize("name", ["APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError"])
def test_sdk_errors_are_transient(name: str) -> None:
    assert is_transient(_error(name))


@pytest.mark.parametrize(
    ("wrapper", "sdk_error"),
    [
        ("OpenAITimeoutError", "APITimeoutError"),
        ("OpenAIConnectionError", "APIConnectionError"),
        ("OpenAIRateLimitError", "RateLimitError"),
        ("OpenAIAPIError", "InternalServerError"),
    ],
)
def test_langchain_wrappers_of_sdk_errors_are_transient(wrapper: str, sdk_error: str) -> None:
    assert is_transient(_error(wrapper, type(sdk_error, (Exception,), {})))


def test_other_errors_are_not_transient() -> None:
    assert not is_transient(_error("BadRequestError"))
    assert not is_transient(ValueError("boom"))

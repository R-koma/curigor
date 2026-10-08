import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from core import config as app_config
from graph.version import GRAPH_VERSION
from observability import langfuse_tracing


@pytest.fixture(autouse=True)
def _disabled_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """キー未設定（＝送出無効）を既定にする。テストから Langfuse へ送らせない。"""
    monkeypatch.setattr(langfuse_tracing, "_client", None)


def test_build_graph_config_carries_thread_id_and_trace_attributes() -> None:
    session_id = uuid.uuid4()
    config = langfuse_tracing.build_graph_config(session_id=session_id, user_id="user-001", session_type="learning")

    assert config["configurable"]["thread_id"] == str(session_id)
    assert config["run_name"] == "learning-graph"
    assert config["metadata"]["langfuse_session_id"] == str(session_id)
    assert config["metadata"]["langfuse_user_id"] == "user-001"
    assert config["metadata"]["langfuse_tags"] == ["learning"]
    assert config["metadata"]["graph_version"] == GRAPH_VERSION


def test_build_graph_config_tags_a_trial_session() -> None:
    config = langfuse_tracing.build_graph_config(
        session_id=uuid.uuid4(), user_id="user-001", session_type="learning", trial=True
    )

    assert config["metadata"]["langfuse_tags"] == ["learning", "trial"]


def test_build_graph_config_carries_no_callbacks_itself() -> None:
    """callbacks は trace のルート span が生きている間だけ付く（traced_graph_run 側の責務）。"""
    config = langfuse_tracing.build_graph_config(session_id=uuid.uuid4(), user_id="user-001", session_type="review")

    assert "callbacks" not in config


async def test_traced_graph_run_does_not_mutate_the_session_config() -> None:
    config = langfuse_tracing.build_graph_config(session_id=uuid.uuid4(), user_id="user-001", session_type="learning")

    async with langfuse_tracing.traced_graph_run(config, name="respond-to-user", input="こんにちは") as run:
        run.set_output("応答")
        run_config = run.config

    assert run_config is not config
    assert run_config["configurable"] == config["configurable"]
    assert "callbacks" not in config


async def test_traced_graph_run_adds_no_callbacks_when_tracing_disabled() -> None:
    config = langfuse_tracing.build_graph_config(session_id=uuid.uuid4(), user_id="user-001", session_type="review")

    async with langfuse_tracing.traced_graph_run(config, name="update-review-note", input=None) as run:
        assert "callbacks" not in run.config


def test_init_tracing_is_noop_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_config, "LANGFUSE_PUBLIC_KEY", None)
    monkeypatch.setattr(app_config, "LANGFUSE_SECRET_KEY", None)

    langfuse_tracing.init_tracing()

    assert not langfuse_tracing.is_enabled()


async def test_traced_transcription_is_a_noop_when_tracing_disabled() -> None:
    async with langfuse_tracing.traced_transcription(
        session_id=uuid.uuid4(), user_id="user-001", model="gpt-transcribe", audio_bytes=10
    ) as trace:
        trace.set_output("文字起こし")


async def test_traced_transcription_records_a_generation_on_the_dialogue_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: list[dict[str, Any]] = []
    attributes: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []

    class _Span:
        def update(self, **kwargs: Any) -> None:
            outputs.append(kwargs)

    class _Client:
        @contextmanager
        def start_as_current_observation(self, **kwargs: Any) -> Iterator[_Span]:
            observations.append(kwargs)
            yield _Span()

    @contextmanager
    def _propagate_attributes(**kwargs: Any) -> Iterator[None]:
        attributes.append(kwargs)
        yield

    monkeypatch.setattr(langfuse_tracing, "_client", _Client())
    monkeypatch.setattr("langfuse.propagate_attributes", _propagate_attributes)
    session_id = uuid.uuid4()

    async with langfuse_tracing.traced_transcription(
        session_id=session_id, user_id="user-001", model="gpt-transcribe", audio_bytes=2048
    ) as trace:
        trace.set_output("二分探索")

    assert attributes == [{"session_id": str(session_id), "user_id": "user-001"}]
    assert observations == [
        {
            "as_type": "generation",
            "name": "transcribe-audio",
            "model": "gpt-transcribe",
            "input": {"audio_bytes": 2048},
        }
    ]
    assert outputs == [{"output": "二分探索"}]


async def test_traced_transcription_without_a_session_sets_only_the_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attributes: list[dict[str, Any]] = []

    class _Span:
        def update(self, **kwargs: Any) -> None:
            pass

    class _Client:
        @contextmanager
        def start_as_current_observation(self, **kwargs: Any) -> Iterator[_Span]:
            yield _Span()

    @contextmanager
    def _propagate_attributes(**kwargs: Any) -> Iterator[None]:
        attributes.append(kwargs)
        yield

    monkeypatch.setattr(langfuse_tracing, "_client", _Client())
    monkeypatch.setattr("langfuse.propagate_attributes", _propagate_attributes)

    async with langfuse_tracing.traced_transcription(
        session_id=None, user_id="user-001", model="gpt-transcribe", audio_bytes=2048
    ):
        pass

    assert attributes == [{"session_id": None, "user_id": "user-001"}]


def test_start_speech_trace_is_a_no_op_without_a_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(langfuse_tracing, "_client", None)

    trace = langfuse_tracing.start_speech_trace(session_id=uuid.uuid4(), user_id="u", model="m", characters=3)
    trace.first_byte(120)
    trace.finish(4800)


def test_start_speech_trace_records_first_byte_and_size(monkeypatch: pytest.MonkeyPatch) -> None:
    span = MagicMock()
    client = MagicMock()
    client.start_observation.return_value = span
    monkeypatch.setattr(langfuse_tracing, "_client", client)

    trace = langfuse_tracing.start_speech_trace(session_id=uuid.uuid4(), user_id="u", model="m", characters=3)
    trace.first_byte(120)
    trace.finish(4800)

    kwargs = client.start_observation.call_args.kwargs
    assert (kwargs["as_type"], kwargs["name"], kwargs["model"]) == ("generation", "synthesize-speech", "m")
    span.update.assert_any_call(metadata={"first_byte_ms": 120})
    span.update.assert_any_call(output={"audio_bytes": 4800})
    span.end.assert_called_once()


async def test_traced_synthesis_wraps_the_llm_call_in_a_span_with_a_callback_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: list[dict[str, Any]] = []
    attributes: list[dict[str, Any]] = []

    class _Span:
        def update(self, **kwargs: Any) -> None:
            pass

    class _Client:
        @contextmanager
        def start_as_current_observation(self, **kwargs: Any) -> Iterator[_Span]:
            observations.append(kwargs)
            yield _Span()

    @contextmanager
    def _propagate_attributes(**kwargs: Any) -> Iterator[None]:
        attributes.append(kwargs)
        yield

    class _Handler:
        pass

    monkeypatch.setattr(langfuse_tracing, "_client", _Client())
    monkeypatch.setattr("langfuse.propagate_attributes", _propagate_attributes)
    monkeypatch.setattr("langfuse.langchain.CallbackHandler", _Handler)
    collection_id = uuid.uuid4()

    async with langfuse_tracing.traced_synthesis(user_id="user-001", collection_id=collection_id, note_count=3) as run:
        assert isinstance(run.config["callbacks"][0], _Handler)

    assert attributes == [{"user_id": "user-001", "tags": ["synthesis"]}]
    assert observations == [
        {
            "as_type": "chain",
            "name": "generate-collection-synthesis",
            "input": {"collection_id": str(collection_id), "note_count": 3},
        }
    ]


async def test_traced_synthesis_is_a_noop_when_tracing_disabled() -> None:
    async with langfuse_tracing.traced_synthesis(user_id="u", collection_id=uuid.uuid4(), note_count=2) as run:
        assert "callbacks" not in run.config

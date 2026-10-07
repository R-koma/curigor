"""Langfuse への LLM トレース送出。

LangGraph の実行 config に CallbackHandler を差し込むだけで、ノード・LLM 呼び出しの
入出力/モデル/トークン数は自動で記録される。ここが持つのは「trace をどう意味付けるか」
（session / user / タグ / trace 名 / trace の入出力）だけで、計測自体は Langfuse の
LangChain 統合に任せる。

グラフ実行を自前の root span で包んでいるのは、LangGraph の実行そのものを root にすると
trace の入出力が LearningState 丸ごと（かつ再開ターンでは入力 None）になり、一覧や評価器
から読めないため。root span には「ユーザー発話 → アシスタント応答」だけを載せる。

キーが未設定の環境（CI・未設定のローカル）でも起動できるよう、その場合は span も
ハンドラも作らず、呼び出し側は分岐なしで同じ経路を通る。
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import UUID

from core import config
from graph.version import GRAPH_VERSION

logger = logging.getLogger(__name__)

_client: Any = None


def is_enabled() -> bool:
    return _client is not None


def init_tracing() -> None:
    """プロセス起動時に一度だけ Langfuse クライアントを初期化する。

    キーは環境変数からの暗黙読み込みに頼らず明示的に渡す。import 順によっては
    load_dotenv() より先に Langfuse が初期化され、認証情報を取り逃すため。
    """
    global _client

    if _client is not None:
        return

    if not (config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY):
        logger.info("Langfuse keys not configured; LLM tracing disabled")
        return

    from langfuse import Langfuse

    _client = Langfuse(
        public_key=config.LANGFUSE_PUBLIC_KEY,
        secret_key=config.LANGFUSE_SECRET_KEY,
        base_url=config.LANGFUSE_BASE_URL,
        environment=config.LANGFUSE_TRACING_ENVIRONMENT,
        release=f"graph-v{GRAPH_VERSION}",
    )
    logger.info("Langfuse tracing enabled (environment=%s)", config.LANGFUSE_TRACING_ENVIRONMENT)


def shutdown_tracing() -> None:
    """未送信のトレースを送り切ってからクライアントを閉じる。

    送出はバックグラウンドのバッチ処理なので、これを省くと終了間際のトレースが落ちる。
    """
    global _client

    if _client is None:
        return

    try:
        _client.shutdown()
    except Exception as exc:  # noqa: BLE001 - トレース送出の失敗でシャットダウンを止めない
        logger.warning("failed to shut down Langfuse client: %s", exc)
    finally:
        _client = None


def build_graph_config(
    *,
    session_id: UUID,
    user_id: str,
    session_type: Literal["learning", "review", "synthesis"],
) -> dict[str, Any]:
    """LangGraph 実行 config（checkpoint の thread_id + Langfuse のトレース属性）を組み立てる。

    metadata の `langfuse_*` キーは LangChain 統合が trace 属性として解釈する予約キー。
    対話セッション1件を Langfuse の session として束ね、1ターン＝1 trace になる
    （グラフは interrupt_before で毎ターン中断するため、ターンごとに実行が切れる）。
    """
    return {
        "configurable": {"thread_id": str(session_id)},
        "run_name": f"{session_type}-graph",
        "metadata": {
            "langfuse_session_id": str(session_id),
            "langfuse_user_id": user_id,
            "langfuse_tags": [session_type],
            "graph_version": GRAPH_VERSION,
        },
    }


class TracedRun:
    """1回のグラフ実行に対応する trace。`config` をそのままグラフに渡す。"""

    def __init__(self, config: dict[str, Any], span: Any) -> None:
        self.config = config
        self._span = span

    def set_output(self, output: Any) -> None:
        """trace の出力（＝一覧や評価器が読む値）を確定させる。"""
        if self._span is not None:
            self._span.update(output=output)


@asynccontextmanager
async def traced_graph_run(
    graph_config: dict[str, Any],
    *,
    name: str,
    input: Any,
    as_type: Literal["agent", "chain"] = "agent",
) -> AsyncIterator[TracedRun]:
    """グラフ実行を Langfuse の root span で包み、実行用 config を渡す。

    trace 名はダッシュボードや評価器が参照するキーになるため、実行ごとに変わる値
    （ID・ターン番号）は入れず、操作を表す固定名だけを使う。
    """
    run_config = dict(graph_config)

    if _client is None:
        yield TracedRun(run_config, None)
        return

    from langfuse import propagate_attributes
    from langfuse.langchain import CallbackHandler

    metadata = graph_config["metadata"]
    with propagate_attributes(
        session_id=metadata["langfuse_session_id"],
        user_id=metadata["langfuse_user_id"],
        tags=metadata["langfuse_tags"],
    ):
        with _client.start_as_current_observation(as_type=as_type, name=name, input=input) as span:
            run_config["callbacks"] = [CallbackHandler()]
            yield TracedRun(run_config, span)


class TracedTranscription:
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_output(self, output: str) -> None:
        if self._span is not None:
            self._span.update(output=output)


@asynccontextmanager
async def traced_synthesis(*, user_id: str, collection_id: UUID, note_count: int) -> AsyncIterator[TracedRun]:
    run_config: dict[str, Any] = {}

    if _client is None:
        yield TracedRun(run_config, None)
        return

    from langfuse import propagate_attributes
    from langfuse.langchain import CallbackHandler

    with propagate_attributes(user_id=user_id, tags=["synthesis"]):
        with _client.start_as_current_observation(
            as_type="chain",
            name="generate-collection-synthesis",
            input={"collection_id": str(collection_id), "note_count": note_count},
        ) as span:
            run_config["callbacks"] = [CallbackHandler()]
            yield TracedRun(run_config, span)


@asynccontextmanager
async def traced_transcription(
    *,
    session_id: UUID | None,
    user_id: str,
    model: str,
    audio_bytes: int,
) -> AsyncIterator[TracedTranscription]:
    if _client is None:
        yield TracedTranscription(None)
        return

    from langfuse import propagate_attributes

    with propagate_attributes(session_id=str(session_id) if session_id else None, user_id=user_id):
        with _client.start_as_current_observation(
            as_type="generation", name="transcribe-audio", model=model, input={"audio_bytes": audio_bytes}
        ) as span:
            yield TracedTranscription(span)


class SpeechTrace:
    def __init__(self, span: Any) -> None:
        self._span = span

    def first_byte(self, milliseconds: int) -> None:
        if self._span is not None:
            self._span.update(metadata={"first_byte_ms": milliseconds})

    def finish(self, audio_bytes: int) -> None:
        if self._span is not None:
            self._span.update(output={"audio_bytes": audio_bytes})
            self._span.end()


def start_speech_trace(*, session_id: UUID, user_id: str, model: str, characters: int) -> SpeechTrace:
    if _client is None:
        return SpeechTrace(None)

    from langfuse import propagate_attributes

    with propagate_attributes(session_id=str(session_id), user_id=user_id):
        span = _client.start_observation(
            as_type="generation", name="synthesize-speech", model=model, input={"characters": characters}
        )
    return SpeechTrace(span)


@asynccontextmanager
async def traced_embedding(*, user_id: str, note_id: UUID, model: str, characters: int) -> AsyncIterator[None]:
    if _client is None:
        yield
        return

    from langfuse import propagate_attributes

    with propagate_attributes(user_id=user_id, tags=["embedding"]):
        with _client.start_as_current_observation(
            as_type="generation",
            name="embed-note",
            model=model,
            input={"note_id": str(note_id), "characters": characters},
        ):
            yield


@asynccontextmanager
async def traced_related_notes_query(*, model: str, characters: int) -> AsyncIterator[None]:
    if _client is None:
        yield
        return

    with _client.start_as_current_observation(
        as_type="generation",
        name="embed-related-notes-query",
        model=model,
        input={"characters": characters},
    ):
        yield

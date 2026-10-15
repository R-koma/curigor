from typing import Protocol


class ObjectStorage(Protocol):
    """対話添付（画像など）のバイナリ永続化先の抽象。

    ローカル開発はファイルシステム、本番は S3 等に差し替える（#128）。LLM へは
    base64 で渡す方針のため、本インターフェースは公開 URL ではなくバイト列の
    put/get を最小機能として持つ。
    """

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def delete_prefix(self, prefix: str) -> None: ...

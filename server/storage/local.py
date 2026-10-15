import asyncio
import shutil
from pathlib import Path


class LocalObjectStorage:
    """ファイルシステムを使う `ObjectStorage` 実装（開発・テスト用）。

    本番では `localhost` のファイルは OpenAI から到達不可だが、画像は base64 で
    渡すため到達性は不要。永続化と履歴再表示のためにのみ使う。
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()

    def _resolve(self, key: str) -> Path:
        target = (self._base / key).resolve()
        if target != self._base and self._base not in target.parents:
            raise ValueError("Invalid storage key")
        return target

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(self._write, path, data)

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(lambda: path.unlink(missing_ok=True))

    async def delete_prefix(self, prefix: str) -> None:
        path = self._resolve(prefix)
        if path == self._base:
            raise ValueError("Invalid storage key")
        await asyncio.to_thread(self._remove_tree, path)

    async def list_child_prefixes(self, prefix: str) -> list[str]:
        path = self._resolve(prefix)
        return await asyncio.to_thread(self._list_dirs, path)

    @staticmethod
    def _list_dirs(path: Path) -> list[str]:
        if not path.is_dir():
            return []
        return [child.name for child in path.iterdir() if child.is_dir()]

    @staticmethod
    def _remove_tree(path: Path) -> None:
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            pass

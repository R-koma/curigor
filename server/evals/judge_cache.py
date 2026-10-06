"""judge の判定を、送った内容のハッシュで保存して使い回す。

基準・入力・応答・モデルのどれかが変われば鍵が変わるので、変えた assertion だけを採点し直す。
同じ入力に対する判定の揺れを見たいときは `--no-judge-cache` で読まずに採点する。
"""

import json
import os
from pathlib import Path
from typing import Any

from evals.checkpoint import sha256_bytes


class JudgeCache:
    def __init__(self, directory: Path, *, read: bool = True) -> None:
        self._directory = directory
        self._read = read

    @staticmethod
    def key(model: str, schema: dict[str, Any], prompt: str) -> str:
        material = json.dumps([model, schema, prompt], ensure_ascii=False, sort_keys=True)
        return sha256_bytes(material.encode("utf-8"))

    def _path(self, key: str) -> Path:
        return self._directory / key[:2] / f"{key}.json"

    def load(self, key: str) -> dict[str, Any] | None:
        if not self._read:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return loaded

    def save(self, key: str, value: dict[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

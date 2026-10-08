"""文字起こしの評価用の音声セットを録音するローカルの画面。

bind は loopback 固定。無認証で `--audio-dir` へ書き込むため、外部に出す経路を作らない。
"""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

import uvicorn

from evals.tools.record_audio.app import create_app
from evals.transcription import DEFAULT_DATASET

_HOST = "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(prog="evals.tools.record_audio", description="評価用の音声を録音する")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument("--no-browser", action="store_true", help="起動時にブラウザを開かない")
    args = parser.parse_args()

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    url = f"http://{_HOST}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, (url,)).start()
    print(f"録音の画面: {url}（保存先: {args.audio_dir}）")
    uvicorn.run(create_app(args.dataset, args.audio_dir), host=_HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

---
paths:
  - "server/storage/**"
  - "server/graph/multimodal.py"
  - "server/repositories/dialogue_message_image_repository.py"
  - "client/lib/image.ts"
---

# 画像添付（マルチモーダル）

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。添付画像の保存・LLM への受け渡し・配信を触る前に関係すると分かっているときは先に読む。

- 対話の `user_message` に画像（JPEG/PNG/WebP・最大4枚・各5MB）を添付できる。クライアントは送信前に長辺2048pxへ縮小し base64 で送る（`client/lib/image.ts`）
- バイナリは `storage/`（dev: ローカルFS、本番: S3 は #128）に保存し、参照メタは `dialogue_message_images` テーブルに持つ。state（チェックポイント）には base64 を載せず storage_key 参照のみ保持し、LLM 呼び出し直前にストレージから読んで base64 data URL を組む（`graph/multimodal.py`）
- LLM へは最新ユーザーメッセージの画像のみ `image_url`（detail=high）ブロックで渡す（会話履歴はプロンプト本文に文字列化されるため）。ノート/フィードバック生成には画像を渡さない
- 履歴の画像は `GET /api/dialogue-sessions/{id}/images/{image_id}` で配信（Bearer 認証必須のためフロントは `fetchImageObjectURL()` で取得）
- 環境変数: `STORAGE_BACKEND`（既定 `local`）・`LOCAL_STORAGE_DIR`（既定 `storage_data`）
- 動画は対象外（音声は `.claude/rules/voice.md`）

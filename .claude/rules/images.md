---
paths:
  - "server/storage/**"
  - "server/graph/multimodal.py"
  - "server/repositories/dialogue_message_image_repository.py"
  - "client/lib/image.ts"
  - "server/api/routes/avatar.py"
  - "client/lib/avatar.ts"
  - "client/components/layout/avatar-settings-modal.tsx"
---

# 画像添付（マルチモーダル）

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。添付画像の保存・LLM への受け渡し・配信を触る前に関係すると分かっているときは先に読む。

- 対話の `user_message` に画像（JPEG/PNG/WebP・最大4枚・各5MB）を添付できる。クライアントは送信前に長辺2048pxへ縮小し base64 で送る（`client/lib/image.ts`）
- バイナリは `storage/`（dev: ローカルFS、本番: S3 互換の Railway の Buckets。ADR-020）に保存し、参照メタは `dialogue_message_images` テーブルに持つ。state（チェックポイント）には base64 を載せず storage_key 参照のみ保持し、LLM 呼び出し直前にストレージから読んで base64 data URL を組む（`graph/multimodal.py`）
- LLM へは最新ユーザーメッセージの画像のみ `image_url`（detail=high）ブロックで渡す（会話履歴はプロンプト本文に文字列化されるため）。ノート/フィードバック生成には画像を渡さない
- 履歴の画像は `GET /api/dialogue-sessions/{id}/images/{image_id}` で配信（Bearer 認証必須のためフロントは `fetchImageObjectURL()` で取得）
- 環境変数: `STORAGE_BACKEND`（既定 `local`。本番は `s3`）・`LOCAL_STORAGE_DIR`（既定 `storage_data`）・`S3_BUCKET`・`S3_ENDPOINT_URL`・`S3_REGION`（既定 `auto`）・`S3_ACCESS_KEY_ID`・`S3_SECRET_ACCESS_KEY`・`S3_ADDRESSING_STYLE`（既定 `virtual`。Railway の新しい Bucket は virtual-hosted）
- `S3ObjectStorage` は無いキーの `get` で `FileNotFoundError` を投げる（`LocalObjectStorage` と揃える）。テストは moto のサーバー（`ThreadedMotoServer`。実際の HTTP で S3 の API を話す）に対して行う（`tests/unit/test_s3_storage.py`）
- アバターは server が保存・配信する（`api/routes/avatar.py`）。キーは `avatars/{user_id}/{uuid}.{ext}` で、保存のたびに前のものを消す。形式は実バイトで JPEG/PNG/WebP だけ（GIF は受け付けない）、最大 5MB。配信は `<img src>` から読むので認証を付けず、ファイル名の UUID で推測を防ぎ、`immutable` でキャッシュさせる。`user.image` には API のオリジンを付けた完全な URL を入れ、CSP の `img-src` に API のオリジンを許可している（`client/lib/csp.ts`）
- アカウントの削除（ADR-016）は server の `purge_user_data` がアバターも消す
- 動画は対象外（音声は `.claude/rules/voice.md`）

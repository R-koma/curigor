---
paths:
  - "server/embedding/**"
  - "server/services/note_embedding.py"
  - "server/services/related_notes.py"
  - "server/services/collection_suggestion.py"
  - "server/services/collection_synthesis.py"
  - "server/services/note_links.py"
  - "server/repositories/note_*_repository.py"
  - "server/repositories/collection_synthesis_repository.py"
  - "server/repositories/feedback_repository.py"
  - "server/api/routes/note.py"
  - "server/api/routes/note_collection.py"
  - "server/api/routes/note_revision.py"
  - "server/api/routes/feedback.py"
  - "server/scripts/**"
  - "server/graph/aspect_map.py"
  - "server/graph/intake_summary.py"
  - "server/graph/nodes/generate_note.py"
  - "server/graph/nodes/generate_feedback.py"
  - "server/graph/nodes/_aspect_map_generation.py"
  - "server/graph/nodes/_feedback_assessment.py"
  - "server/graph/prompts/note.py"
  - "server/graph/prompts/feedback.py"
  - "server/graph/prompts/collection.py"
  - "server/graph/prompts/synthesis.py"
  - "client/app/(main)/notes/**"
  - "client/app/(main)/collections/**"
  - "client/components/notes/**"
  - "client/components/collections/**"
  - "client/lib/note-links.ts"
  - "client/lib/collections.ts"
  - "client/lib/aspect-map.ts"
---

# ノート・フィードバック・まとめノート・埋め込み

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。ノートの生成と更新・観点マップ・埋め込みと候補・まとめノートを触る前に関係すると分かっているときは先に読む。

## ノートの埋め込み（pgvector）

- ノートの埋め込みは `note_embeddings`（`note_id` が PK、`vector(1536)`、`model`、`content_hash`）に持つ。入力は topic・summary・content・`note_revisions` の本文を連結したもの（`services/note_embedding.py` の `build_embedding_text`）
- 作り直すのは、ノートの生成（`generate_note`）・復習による更新（`update_note_and_feedback`）・手での本文編集（`PATCH /api/notes/{id}`）の後で、どれも `schedule_note_embedding` でバックグラウンドに回す。`content_hash`（モデル名 + 入力のハッシュ）が同じなら API を呼ばない。失敗してもノートの保存は成功させ、次の更新か `uv run python -m scripts.backfill_note_embeddings` で作り直す。ノートの本文を変える経路を足したら、ここにも呼び出しを足すこと
- 近傍検索は同じユーザー・同じ `model` の埋め込みだけを比べる。モデルを変えたら backfill で作り直す（`find_note_ids_without_embedding` は `model` 違いを未作成として拾う）
- asyncpg に vector 型のコーデックを登録せず、`$n::vector` に `[0.1,...]` の文字列を渡す（`note_embedding_repository._to_vector_literal`）
- **束ね先の候補はベクトルでも入れる**（`services/collection_suggestion.py` の `suggest_collection_by_similarity`）。埋め込みを作り直した直後（`refresh_note_embedding` の末尾）と、`backfill_note_embeddings` の 2 周目で呼ぶ。近い `COLLECTION_SUGGESTION_NEIGHBORS` 件のうち、類似度が `COLLECTION_SUGGESTION_MIN_SIMILARITY` 以上でまとめノートに入っているものを、まとめノートごとに類似度の合計で比べ、最上位の名前を `notes.suggested_collection` に入れる。画面の候補のバナーと「入れない」の操作は、生成時の LLM の候補と共通
- 候補を入れるのは、束ねておらず・候補も無く・`collection_suggestion_dismissed_at` が無いノートだけ（`set_suggested_collection_if_unsuggested` が 1 文で判定する）。生成時の LLM の候補があればそちらを優先する。候補を断ったとき（`clear_suggested_collection`）と、まとめノートから外したとき（`set_collection(None)`）に `collection_suggestion_dismissed_at` を立て、以後は自動で提案しない。これが無いと、断った候補がノートの編集のたびに戻る
- `COLLECTION_SUGGESTION_MIN_SIMILARITY`（既定 0.5）は実データで決めた暫定値で、改善の余地がある。測り方・調整の目安・改善案は `docs/collection-suggestion.md`
- **ノートどうしのつながりの候補も埋め込みで作る**（`services/note_links.py` の `suggest_note_links`）。束ね先の候補と同じく、埋め込みを作り直した直後と `backfill_note_embeddings`（埋め込みのある全ノート）で呼ぶ。同じまとめノートのノートは除き、近い `NOTE_LINK_LIMIT` 件のうち類似度 `NOTE_LINK_MIN_SIMILARITY`（暫定 0.6）以上を `note_links` に `suggested` で入れる。1 組を 1 行で持ち（`note_id_a < note_id_b`）、両方のノートの詳細に出る。作り直しでは類似度だけを更新し、採否（`accepted` / `dismissed`）は変えないので、断った候補は戻らない。下限を下回った未回答の候補は消す。候補を作った後に両方を同じまとめノートに入れたら、未回答の候補は表示しない（行は残す）
- Langfuse には `traced_embedding()` が `embed-note`（generation）として user だけに紐づけて送る
- 環境変数: `EMBEDDING_MODEL`（既定 `text-embedding-3-small`）。次元数 `EMBEDDING_DIMENSIONS` はマイグレーションの `vector(1536)` と一致させる

## ノートの生成と観点マップ

- **ノートの観点マップの ID は保存済み JSON の並び順から振る**（`graph/aspect_map.py` の `with_aspect_ids`。`a1` / `a1-2`。API の `NoteResponse.aspect_map` が付けて返す）。`feedbacks.improvement_items`（JSONB。`improvements` の行と 1:1）がこの ID で改善点と観点を結びつけるので、保存済みの `notes.aspect_map` を並べ替え・作り直す経路を足すときは結びつきも作り直すこと。学習の観点マップと対話分析はノートの中身を使わないので、`generate_note` がノート本文と並行に作り、観点マップはノートと一緒に保存し、分析と観点マップは state の `feedback_inputs` で `generate_feedback` に渡す（`generate_feedback` は採点だけを行い、受け取った観点マップで改善点を結びつける）。分析に失敗したら `feedback_inputs` は `None` で、`generate_feedback` が今までどおり分析と観点マップを作り直す。観点マップが失敗したら結びつけずにフィードバックだけ保存する。終了後の待ち時間は `scripts/measure_generation_latency.py` で、同じセッションを繰り返して計測する（#582）。学習中の深さの地図（`depth_map`）の ID はクライアントへ送らないが、ノートの観点マップの ID は学習の後に使うだけで内容を含まないので送ってよい。LLM が返した `aspect_id` は観点マップに実在するものだけを残す（`link_improvements`）
- **ノート本文は学習者が説明した内容と AI の補足を分ける**: 任意の節 `## AIの補足`（「重要なポイント」と「まだ曖昧な点」の間）に、学習者が自分の言葉で説明していない用語・定義を置き、「学んだこと」「重要なポイント」には書かない。生成（`GENERATE_NOTE_PROMPT`）・改訂（`UPDATE_NOTE_PROMPT`。復習で説明できた項目は「学んだこと」へ移す）・復習の追記（`APPEND_REVIEW_PROMPT`）・フィードバック（`GENERATE_FEEDBACK_PROMPT`。良かった点の根拠にしない）の 4 つで同じ区別を使う。節名を変えるときは 4 つをそろえる
- **学習の前提はノート作成時に `notes.intake`（JSONB）へ保存し、ノート詳細の観点マップ（`NoteAspectMap`）の下にたたんで出す**: 値は `generate_note` が state から `build_intake_summary`（`graph/intake_summary.py`。学習中の進捗と同じ正規化）で組み、3 項目とも空なら NULL。復習セッション（`update_note_and_feedback`）は触らない。聞き取りを導入する前のノートと、この機能より前のノートはバックフィルしない（チェックポイントは前提の正本にならない）ので `intake` が NULL のまま表示しない。`NoteAspectMap` は観点が空だとセクションごと出さないため、観点マップの生成中・失敗時は前提も出ない

## 注意事項

- **フィードバックは 1 ノートに複数行（評価の履歴）**: 学習の `generate_feedback` も復習の `update_note_and_feedback` も `feedbacks` へ追記する。最新の評価は `find_by_note_id`（`created_at` の昇順）の末尾で、復習の重点（`prior_improvements`）・セッション詳細はこれを `feedbacks[-1]` で読む。並び順を変えるとこれらが古い評価を読む。`improvement_items` が NULL の行は結びつきを導入する前のもので、改善点の本文だけを今までどおり表示する
- **まとめノート（`note_collections`）とカテゴリー（`notes.category`）は別の概念**: カテゴリーは分野（「OS」など）で一覧の絞り込み用、まとめノートはまとめの単位（本 1 冊など）。画面では「まとめノート」と呼び、コード上の名前は `collection` のまま（「テーマ」は配色の切り替えと紛らわしいため画面では使わない）。まとめノートの候補（`notes.suggested_collection`）は生成時の推定で、ユーザーが確定するまで `collection_id` を入れない
- **まとめの下書きが古いかは内容ハッシュで判定する**: `notes.updated_at` は観点マップの保存でも動くので使えない。`notes.content` と `note_revisions` の本文を順に連結した SHA-256 を、生成時に `collection_syntheses.source_notes` へ保存し、表示時に比べる（`services/collection_synthesis.py`）。ノートの本文を変える経路を足したら、ハッシュの入力に含まれているか確かめること
- **ノートの手での編集の上限はクライアントの入力欄と一致させる**: `PATCH /api/notes/{id}` の `topic` は聞き取りの `MAX_TOPIC_ANSWER_LENGTH`、`summary` / `content` / `category` は `schemas/note.py` の `MAX_NOTE_*_LENGTH` で 422 にする。`note-edit-form.tsx` と `note-category-editor.tsx` の `maxLength` はこの値を写したもので、変えるときは両方をそろえる

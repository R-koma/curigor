# 横の質問（「理解する」セッション） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「理解する」（`explore`）セッションで、AI の応答の一部を選んで右の欄で質問でき、その内容が本筋の AI と学習メモに伝わるようにする。

**Architecture:** 横の質問は LangGraph の本筋を通さず、DB の 2 つのテーブルと REST（回答は NDJSON のストリーム）で持つ。箇所は「どの応答の・どの文字列の・何番目か」で保存し、クライアントは描画後の文字から範囲を探して CSS Custom Highlight API で下線を引く（DOM を書き換えないので、Markdown の再描画で消えない）。本筋の応答と学習メモの生成は、同じテーブルから横の質問を読む。

**Tech Stack:** FastAPI + asyncpg + Alembic、LangChain（`graph/llm.py` の `llm` / `llm_structured`）、Next.js 16 + React 19 + Vitest、CSS Custom Highlight API。

**Spec:** `docs/superpowers/specs/2026-11-12-side-questions-design.md`（見本: `docs/superpowers/specs/2026-11-12-side-questions-mockup.html`。画面の正は見本）

## Global Constraints

- 入れるのは `session_type == "explore"` だけ。`learning`・`review`・`synthesis` の画面とプロンプトには何も足さない。
- 本筋のチェックポイントを横の質問で進めない。`GRAPH_VERSION` は上げない。state にフィールドを足さない。
- WebSocket は項目の追加だけにし、`PROTOCOL_VERSION` は上げない。
- 選べる文字数は 300 字まで。子の深さは 3 段まで（本筋の箇所についた質問を深さ 0 とし、深さ 3 の回答からは作れない）。
- 横の質問 1 回の送信は `LlmOperation` の `turn` で数える（`llm_usages` の CHECK 制約は変えない）。記録は LLM を呼ぶ前、返すのは LLM を呼ばずに終わったと確かなときだけ。
- 利用者のデータを外部へ送る REST ルートは `ConsentedUser`。LLM を待つ間 `DB` 依存でコネクションを借り続けない（`get_pool()` から必要な間だけ `acquire()`）。
- リポジトリ関数の接続引数は `core.database.DBConnection`。SQL の値はプレースホルダで渡す。
- スマホ幅（`md:` 未満）とタッチ端末（`pointer-coarse:`）では、ボタン・右の欄・下線を出さない。
- 色・文字サイズ・重なり順はトークンで書く。アイコンだけのボタンは `aria-label` と `TooltipLabel`。見本の CSS は写さず、アプリの部品とトークンで組み直す。
- 画面に「往復」などの回数の文字を出さない。「すべて畳む」はアイコンのボタン。
- コメントは既定で書かない（`CLAUDE.md` の「コメント」）。規約は `.claude/rules/` に書く。
- 課金の eval は作らない・走らせない。
- マイグレーションを足すので、テストは共有の `curigor_test` ではなく、このブランチ専用の DB で走らせる。PR の前に main の新しいマイグレーションを確かめ、`down_revision` を合わせる（今の head は `d2a6f8b4c1e7`）。
- コミットは英語の Conventional Commits（例: `feat(explore): ...`）。PR の本文に `## ドキュメントの更新` の節を入れる。

## Review Focus

1. **同じ文字列が応答の中に何度も出る**: 2 回目の「索引」を選んだら、2 回目に下線が付く（1 回目ではない）。→ Task 7 のテスト。
2. **太字・リンク・インラインコードをまたぐ選択（同じ段落の中）**: 質問でき、再読み込み後も同じ範囲に下線が付く。→ Task 7 のテスト。
3. **横の回答のストリーム中に、もとの本筋の応答が取り消される**: ストリームはエラーで終わり、行は残らない（外部キーのカスケード）。500 にならない。→ Task 3 のテスト。
4. **終わった・`abandoned` のセッションへの送信**: 409 で断る。LLM を呼ばず、上限の回数も返す。→ Task 3 のテスト。
5. **新しい項目の無い古い学習メモ**: 今までどおり読めて、編集しても壊れない。→ Task 5・Task 10 のテスト。

---

## 始める前に

- [ ] issue は #828（担当と着手のコメントは付けてある）。PR の本文には `Closes #828` を書く。
- [ ] ブランチは `feat/explore-side-questions`（作成済み。この計画・設計書・見本を載せたコミットが 1 つある）。このブランチに積む。
- [ ] `git fetch origin` で main の新しいコミットとマイグレーションを見る（`alembic heads` で head を確かめる）。
- [ ] 先に読む規約: `.claude/rules/server/graph.md`・`server/langfuse.md`・`client/session.md`・`client/ui.md`・`docs/design/ui-guidelines.md`。
- [ ] `docs/superpowers/` は gitignore 済みで、main には入れない。PR を作る前に、最後のコミットで 3 ファイルを `git rm --cached` で外す（Task 11）。

## ファイルの地図

| ファイル | 役割 |
| --- | --- |
| `server/migrations/versions/<rev>_create_side_questions.py`（新規） | 2 つのテーブル |
| `server/repositories/side_question_repository.py`（新規） | 横の質問とメッセージの SQL |
| `server/schemas/side_question.py`（新規） | リクエスト・レスポンス・ストリームのイベント |
| `server/graph/prompts/side_question.py`（新規） | 横の AI のプロンプトと、本筋・メモに渡す文の組み立て |
| `server/services/side_question.py`（新規） | 文脈の組み立て・ストリーム・保存・失敗時の片付け・Langfuse の span |
| `server/api/routes/side_question.py`（新規） | REST の 3 ルート |
| `server/graph/nodes/_explore_dialogue.py` | 本筋のプロンプトに横の質問を入れる |
| `server/graph/nodes/generate_study_memo.py`・`_explore_llm.py`・`graph/explore.py` | 学習メモへの振り分け |
| `server/schemas/study_memo.py`・`services/study_memo_edit.py` | 学習メモの項目の追加と編集での保持 |
| `client/lib/side-questions.ts`（新規） | 型・API・NDJSON の読み取り |
| `client/lib/text-anchor.ts`（新規） | 選択 → 箇所、箇所 → 範囲 |
| `client/lib/side-question-tree.ts`（新規） | 開閉・下書き・並び順の純粋な関数 |
| `client/hooks/use-side-questions.ts`（新規） | 状態と送信 |
| `client/components/chat/side-questions/*`（新規） | ボタン・右の欄・枠・子・入力欄・下線 |
| `client/app/(main)/learn/page.tsx`・`hooks/use-chat-websocket.ts` | 応答の ID と、画面への組み込み |
| `client/lib/study-memos.ts`・`components/study-memos/*` | 学習メモでの見せ方と編集 |

---

### Task 1: テーブルとリポジトリ

**Files:**
- Create: `server/migrations/versions/<rev>_create_side_questions.py`
- Create: `server/repositories/side_question_repository.py`
- Test: `server/tests/unit/test_side_question_repository.py`

**Interfaces:**
- Produces（テーブル）:
  - `side_questions`: `id UUID PK`、`dialogue_session_id TEXT NOT NULL REFERENCES dialogue_sessions(id) ON DELETE CASCADE`、`parent_id UUID REFERENCES side_questions(id) ON DELETE CASCADE`、`anchor_message_id TEXT REFERENCES dialogue_messages(id) ON DELETE CASCADE`、`anchor_side_message_id UUID REFERENCES side_question_messages(id) ON DELETE CASCADE`、`quote TEXT NOT NULL`、`occurrence INTEGER NOT NULL`（0 始まり）、`depth INTEGER NOT NULL CHECK (depth BETWEEN 0 AND 3)`、`created_at`。CHECK: `anchor_message_id` と `anchor_side_message_id` のちょうど一方が NULL でない。`parent_id IS NULL` は `anchor_message_id IS NOT NULL` と同値。
  - `side_question_messages`: `id UUID PK`、`side_question_id UUID NOT NULL REFERENCES side_questions(id) ON DELETE CASCADE`、`role TEXT CHECK (role IN ('user','assistant'))`、`content TEXT NOT NULL`、`message_order INTEGER NOT NULL`、`created_at`。
  - 2 つのテーブルは互いを参照するので、`anchor_side_message_id` の外部キーは 2 つ目のテーブルを作った後に `ALTER TABLE` で足す。
- Produces（関数。どれも第 1 引数は `conn: DBConnection`）:
  - `create(conn, *, dialogue_session_id: UUID, parent_id: UUID | None, anchor_message_id: str | None, anchor_side_message_id: UUID | None, quote: str, occurrence: int, depth: int) -> dict[str, Any]`
  - `find_owned(conn, side_question_id: UUID, user_id: str) -> dict[str, Any] | None`（`dialogue_sessions.user_id` で絞る）
  - `add_message(conn, side_question_id: UUID, role: str, content: str, *, message_id: UUID | None = None) -> dict[str, Any]`（`message_order` は今の最大 + 1）
  - `delete_message(conn, message_id: UUID) -> None`
  - `delete_if_empty(conn, side_question_id: UUID) -> None`
  - `find_threads(conn, dialogue_session_id: UUID) -> list[dict[str, Any]]`（各要素は `side_questions` の列と `messages: list[dict]`。`created_at` 順、メッセージは `message_order` 順。メッセージの無いものは含めない）
  - `find_side_message_owner(conn, side_message_id: UUID) -> dict[str, Any] | None`（その回答が属する横の質問の行。子を作るときに `depth` と `dialogue_session_id` を知る）

- [ ] **Step 1: 失敗するテストを書く**（実 DB。モックしない）

  テスト名と確かめること:
  - `test_create_and_find_threads_returns_messages_in_order`
  - `test_find_threads_excludes_threads_without_messages`
  - `test_find_owned_returns_none_for_other_user`
  - `test_deleting_anchor_dialogue_message_cascades_to_thread_and_children`（本筋の応答の行を消すと、その箇所の質問・子・メッセージが全部消える）
  - `test_deleting_session_cascades`
  - `test_depth_over_3_is_rejected`（`asyncpg.CheckViolationError`）
  - `test_both_anchors_or_neither_is_rejected`

- [ ] **Step 2: 走らせて、失敗を確かめる**

  Run: `uv run pytest tests/unit/test_side_question_repository.py -v`
  Expected: FAIL（モジュールが無い）

- [ ] **Step 3: マイグレーションを書く**（`uv run alembic revision -m "create side questions tables"`。`op.execute` で SQL を直接書く既存の流儀に合わせる。`downgrade` は逆順に落とす）
- [ ] **Step 4: リポジトリを書く**
- [ ] **Step 5: 専用 DB に `alembic upgrade head` して、テストを通す**

  Run: `uv run pytest tests/unit/test_side_question_repository.py -v` → PASS

- [ ] **Step 6: アカウントの削除で消えることを確かめる**（`dialogue_sessions` のカスケードで足りるはず。`DELETE /api/account/data` と BetterAuth の削除のテストがテーブルの一覧を持っていたら足す）
- [ ] **Step 7: Commit**（`feat(explore): add side question tables and repository`）

---

### Task 2: 本筋の応答の ID をクライアントへ渡す

**Files:**
- Modify: `server/repositories/dialogue_message_repository.py`（`insert` に `message_id: UUID | None = None` を足し、渡されたらそれを `id` に使う）
- Modify: `server/schemas/websocket_message.py`（`AssistantMessageEnd` に `message_id: UUID | None = None`）
- Modify: `server/api/websocket/chat.py`（応答を保存する 2 か所: `_start_session` と `_handle_user_message`）
- Modify: `server/api/routes/dialogue_session.py` と、その応答のスキーマ（`GET /{session_id}/messages` の各メッセージに `id: str`）
- Modify: `client/hooks/use-chat-websocket.ts`（`ChatMessage` に `id?: string`。`assistant_message_end` で最後の応答に入れる。`resumeSession` の `initialMessages` にも入る）、メッセージの一覧を `ChatMessage` に変えている所
- Test: `server/tests/integration/test_websocket_chat.py`、`server/tests/unit/` のルートのテスト、`client/__tests__/hooks/`

**Interfaces:**
- Produces: `AssistantMessageEnd.message_id`（保存した応答の `dialogue_messages.id`。保存しない応答では `None`）。`ChatMessage.id`。

- [ ] **Step 1: 失敗するテストを書く**
  - WS: `test_explore_assistant_message_end_carries_saved_message_id`（`assistant_message_end.message_id` が、DB の最後の assistant の行の `id` と同じ。開始のターンと 2 ターン目の両方）
  - REST: メッセージの一覧の各要素に `id` がある
  - client: `assistant_message_end` を受けると、最後の assistant の `ChatMessage.id` が入る
- [ ] **Step 2: 失敗を確かめる**
- [ ] **Step 3: 実装する**。`assistant_message_end` は保存より前に送られるので、ストリームを始める前に `uuid4()` で ID を作り、`AssistantMessageEnd` と `insert(message_id=...)` の両方に同じものを渡す。`_stream_ai_response` の引数に足す。`learning`・`review` でも同じ ID が入ってよい（使わないだけ）。
- [ ] **Step 4: テストを通す**（`uv run pytest tests/integration/test_websocket_chat.py -v`、`npm run test`）
- [ ] **Step 5: Commit**（`feat(chat): expose saved assistant message ids to the client`）

---

### Task 3: 横の質問の REST ルート

**Files:**
- Create: `server/schemas/side_question.py`、`server/graph/prompts/side_question.py`、`server/services/side_question.py`、`server/api/routes/side_question.py`
- Modify: `server/main.py`（ルーターの登録）、`server/graph/llm.py`（`ResponseTask` に `"explore-side-question"` を足し、`RESPONSE_MODELS` に `explore-dialogue` と同じモデルを入れる）、`server/observability/langfuse_tracing.py`（`traced_side_question()`）、`server/api/errors.py`（要る `ErrorCode`）
- Test: `server/tests/unit/test_side_question_route.py`、`server/tests/unit/test_side_question_prompt.py`、`server/tests/integration/test_resource_ownership.py`

**Interfaces:**
- Consumes: Task 1 のリポジトリ、Task 2 の応答の ID。
- Produces（ルート。どれも `ConsentedUser`）:
  - `GET /api/dialogue-sessions/{session_id}/side-questions` → `{"side_questions": [SideQuestionResponse]}`
  - `POST /api/dialogue-sessions/{session_id}/side-questions`（本文 `SideQuestionCreate`）→ NDJSON のストリーム
  - `POST /api/side-questions/{side_question_id}/messages`（本文 `{"content": str}`）→ NDJSON のストリーム
- Produces（スキーマ）:
  - `SideQuestionCreate`: `anchor_message_id: str | None`、`anchor_side_message_id: UUID | None`（ちょうど一方）、`quote: str`（1〜300 字）、`occurrence: int`（0 以上）、`content: str`（1〜`MAX_MESSAGE_CONTENT_LENGTH` 字）
  - `SideQuestionResponse`: `id`、`parent_id`、`anchor_message_id`、`anchor_side_message_id`、`quote`、`occurrence`、`depth`、`messages: [{id, role, content}]`
  - ストリームのイベント（1 行 1 JSON。`media_type="application/x-ndjson"`）:
    `{"type":"started","side_question_id":…,"user_message_id":…,"answer_message_id":…}` → `{"type":"chunk","content":…}` を 0 回以上 → `{"type":"end"}`、または途中で `{"type":"error","code":…,"detail":…}`
- Produces（プロンプト）: `build_side_question_prompt(*, topic: str, anchor_text: str, quote: str, recent_messages: str, ancestors: str, other_side_questions: str) -> str`、`SIDE_QUESTION_PROMPT_FINGERPRINT`、`format_side_questions_for_context(threads: Sequence[Mapping[str, Any]], *, max_chars: int) -> str`（横の質問ごとに「選んだ箇所・質問・答えの先頭 200 字」。新しいものから `max_chars` に収まるだけ。Task 4 も使う）

**規則（ストリームを始める前に確かめ、だめなら `ApiError`）:**

| 条件 | 応答 |
| --- | --- |
| セッションが無い・他のユーザーのもの、横の質問が無い・他のユーザーのもの | 404 |
| `session_type` が `explore` でない | 409 |
| セッションが進行中でない（終了・`abandoned`・メモの生成中） | 409 |
| `anchor_message_id` がそのセッションの assistant の行でない、`anchor_side_message_id` がそのセッションの横の assistant の回答でない | 404 |
| 親の `depth` が 3（子を作ると 4 になる） | 422 |
| `quote` が、箇所の応答の本文に含まれない（Markdown の記号を除いた照合はしない。空白を詰めた文字列どうしで `in` を見る。含まれなくても断らず保存する。描画後の文字と元の Markdown は一致しないことがあるため） | 断らない |
| 1 日の上限（`turn`）を超えた | 既存の発言の上限と同じ `code` と状態 |

**流れ:** 検証 → 上限を予約 → 横の質問の行（新規のときだけ）とユーザーのメッセージを保存 → コネクションを返す → `started` を送る → LLM をストリーム（`llm.astream(messages, task="explore-side-question")`。`traced_side_question()` の span で包み、対話セッションの session と user に紐づける）→ 回答を `answer_message_id` で保存 → `end`。

**失敗したとき:** LLM の失敗・クライアントの切断・保存時の外部キー違反（もとの応答が取り消された）では、保存したユーザーのメッセージを消し、横の質問が空になったら消す（`delete_if_empty`）。`error` を送る。上限の回数は返さない。検証で断ったとき（LLM を呼んでいない）だけ返す。

**横の AI に渡す文脈:** (1) 箇所を含む応答の全文、(2) 本筋の直近 8 件（`dialogue_messages` から）、(3) 親・祖先の横の質問のやり取りの全文と、今の横の質問のこれまでのやり取り、(4) 同じセッションのほかの横の質問（`format_side_questions_for_context(..., max_chars=2000)`）。

**プロンプトの中身:** `graph/prompts/explore.py` の `_COMMON_RULES` を再利用する（公開の名前に変えて import する）。足す指示: 選んだ箇所についての疑問に 2〜6 文で答える／選んだ箇所が語 1 つで意味を尋ねられたら、その文脈での意味を答える／本筋とほかの横の質問で説明済みのことは知っている前提でよい／理解を確かめる問いを添えない。

- [ ] **Step 1: 失敗するテストを書く**（ルートのテストは LLM だけを差し替え、DB は実物）
  - `test_create_streams_started_chunks_end_and_saves_both_messages`
  - `test_follow_up_appends_to_existing_thread`
  - `test_child_of_side_answer_gets_parent_and_depth_plus_one`
  - `test_child_at_depth_3_is_rejected_422`
  - `test_non_explore_session_is_rejected_409`
  - `test_ended_session_is_rejected_409_without_llm_call_and_refunds_usage`
  - `test_quote_over_300_chars_is_rejected_422`
  - `test_usage_limit_reached_is_rejected_without_llm_call`
  - `test_llm_failure_emits_error_and_leaves_no_rows_and_keeps_usage`
  - `test_anchor_message_deleted_during_stream_emits_error_and_leaves_no_rows`（ストリームの途中で `dialogue_messages` の行を消す）
  - `test_get_returns_threads_with_messages`
  - プロンプト: `test_prompt_contains_anchor_text_quote_and_ancestors`、`test_context_format_truncates_answers_to_200_chars_and_respects_max_chars`
  - `test_resource_ownership.py` の `RESOURCE_CALLS` に 3 ルートを足す（他人のものは 404 で何も変わらない）
- [ ] **Step 2: 失敗を確かめる**（`uv run pytest tests/unit/test_side_question_route.py tests/unit/test_side_question_prompt.py -v`）
- [ ] **Step 3: スキーマ・プロンプト・サービス・ルートを書く**
- [ ] **Step 4: テストを通す**。続けて `uv run ruff check . --fix && uv run ruff format . && uv run mypy .`
- [ ] **Step 5: Commit**（`feat(explore): add side question endpoints with streamed answers`）

---

### Task 4: 本筋の AI に横の質問を伝える

**Files:**
- Modify: `server/graph/nodes/_explore_dialogue.py`（`respond_explore`）、`server/graph/prompts/explore.py`（`build_explore_dialogue_prompt` に `side_questions: str = ""`）
- Test: `server/tests/unit/` の explore のプロンプトとノードのテスト

**Interfaces:**
- Consumes: `side_question_repository.find_threads`、`format_side_questions_for_context`。

- [ ] **Step 1: 失敗するテストを書く**
  - `test_dialogue_prompt_includes_side_questions_section_when_present`（節の見出しと、選んだ箇所・質問が入る）
  - `test_dialogue_prompt_has_no_side_questions_section_when_empty`（横の質問が無いとき、プロンプトは今と 1 文字も変わらない）
  - `test_respond_explore_reads_side_questions_for_session`（実 DB に横の質問を入れ、LLM に渡ったプロンプトに含まれる）
- [ ] **Step 2: 失敗を確かめる**
- [ ] **Step 3: 実装する**。`respond_explore` が `get_pool()` から `find_threads(conn, state["dialogue_session_id"])` を読み、`format_side_questions_for_context(threads, max_chars=4000)` を渡す。プロンプトの節には「ユーザーは次の箇所について、横で質問して答えを読んでいる。ここで説明済みのことを一から説明し直さない」と書く。読み取りに失敗したら空で続ける（本筋を止めない）。
- [ ] **Step 4: テストを通す**
- [ ] **Step 5: Commit**（`feat(explore): tell the main dialogue what was asked on the side`）

---

### Task 5: 学習メモへの振り分け

**Files:**
- Modify: `server/schemas/study_memo.py`、`server/graph/output_schemas.py`、`server/graph/prompts/explore.py`、`server/graph/nodes/_explore_llm.py`、`server/graph/nodes/generate_study_memo.py`、`server/graph/explore.py`、`server/graph/llm.py`（`StructuredTask` に `"digest-side-questions"`）、`server/services/study_memo_edit.py`、`server/graph/session_end.py` とその呼び出し元
- Test: `server/tests/unit/` の `generate_study_memo`・`study_memo_edit`・`session_end` のテスト

**Interfaces:**
- Produces（スキーマ）:
  - `StudyMemoQuestion` に `quote: str | None = None`、`parent_index: int | None = None`、`from_side: bool = False`
  - `StudyMemoTerm` に `from_side: bool = False`
  - `StudyMemoQuestionEdit`・`StudyMemoTermEdit` は変えない（クライアントは足した項目を送らない。サーバーが元の番号から引き継ぐ）
- Produces（LLM）: `digest_side_questions(topic: str, threads: Sequence[Mapping[str, Any]]) -> dict[UUID, SideQuestionDigest]`。`SideQuestionDigest` は `term: ExploreTermDraft | None` と `question: str`・`answer: str`（疑問が無ければ両方とも空文字）。失敗したら空の dict を返す（そのとき横の質問はメモに載らない）。
- Produces: `has_learner_content(values, *, has_side_questions: bool = False)`。`explore` の分岐だけが `has_side_questions` を見る。

**振り分けの規則（spec の 6 節）:**
- 1 つの横の質問から、用語 1 つと疑問 1 組までを作る。意味を聞いた部分は用語、それ以外は疑問。
- 用語は `merge_terms` で本筋の用語とまとめる。同じ語があれば、横の質問から来た意味で置き換え、`from_side=True` にする。
- 疑問の並び: 本筋の疑問（今までどおり）の後ろに、横の質問から来た疑問を、親 → その子 → その孫の順で置く。`quote` は選んだ箇所、`from_side=True`。
- `parent_index`: いちばん近い祖先のうち疑問を持つものの番号。無ければ `None`。
- `organize_memo` に渡すのは `parent_index` が `None` の疑問だけ。`build_overview` の後で、子の番号を親と同じ観点の `question_indices` に、親のすぐ後ろへ入れる。
- 横の質問を読むのは、もとの本筋の応答が残っているものだけ（取り消された分は外部キーのカスケードで行ごと消えている）。

- [ ] **Step 1: 失敗するテストを書く**（LLM は差し替える）
  - `test_side_question_meaning_becomes_term_marked_from_side`
  - `test_side_question_with_meaning_and_follow_up_yields_term_and_question`
  - `test_side_term_replaces_main_term_with_same_name_without_duplicate`
  - `test_child_question_follows_parent_in_same_aspect_with_parent_index`
  - `test_child_of_term_only_parent_is_organized_as_top_level`
  - `test_digest_failure_keeps_main_memo_unchanged`
  - `test_memo_without_side_questions_is_identical_to_before`（項目の既定値だけが足される）
  - 編集: `test_edit_preserves_quote_parent_and_from_side`、`test_edit_remaps_parent_index_after_deleting_earlier_question`、`test_edit_deleting_parent_clears_parent_index_of_child`
  - 古い行: `test_old_memo_without_new_fields_validates_and_edits`
  - `test_has_learner_content_explore_true_with_only_side_questions`
- [ ] **Step 2: 失敗を確かめる**
- [ ] **Step 3: 実装する**。`has_learner_content` の呼び出し元を全部探し（`grep -rn "has_learner_content(" server --include="*.py"`）、`explore` のセッションでは横の質問の有無（メッセージのある横の質問が 1 件以上）を渡す。グラフのノードの中から呼ぶ所は `get_pool()` で読む。
- [ ] **Step 4: テストを通す**。`uv run mypy .`
- [ ] **Step 5: Commit**（`feat(explore): fold side questions into the study memo`）

---

### Task 6: クライアントの型と API

**Files:**
- Create: `client/lib/side-questions.ts`
- Test: `client/__tests__/lib/side-questions.test.ts`

**Interfaces:**
- Produces:
  - `interface SideMessage { id: string; role: "user" | "assistant"; content: string }`
  - `interface SideQuestion { id: string; parentId: string | null; anchorMessageId: string | null; anchorSideMessageId: string | null; quote: string; occurrence: number; depth: number; messages: SideMessage[] }`
  - `type SideAnchor = { anchorMessageId: string; anchorSideMessageId?: undefined } | { anchorSideMessageId: string; anchorMessageId?: undefined }`
  - `fetchSideQuestions(sessionId: string): Promise<SideQuestion[]>`（`fetchAPI` を使う）
  - `type SideStreamEvent = { type: "started"; sideQuestionId: string; userMessageId: string; answerMessageId: string } | { type: "chunk"; content: string } | { type: "end" } | { type: "error"; code: string; detail: string }`
  - `streamNewSideQuestion(sessionId: string, body: SideAnchor & { quote: string; occurrence: number; content: string }, signal?: AbortSignal): AsyncGenerator<SideStreamEvent>`
  - `streamSideFollowUp(sideQuestionId: string, content: string, signal?: AbortSignal): AsyncGenerator<SideStreamEvent>`
  - `parseNdjson(stream: ReadableStream<Uint8Array>): AsyncGenerator<unknown>`（行の途中でチャンクが切れても正しく読む）
  - `MAX_SIDE_QUOTE_LENGTH = 300`、`MAX_SIDE_DEPTH = 3`

- [ ] **Step 1: 失敗するテストを書く**: `parseNdjson` が、1 行が 2 つのチャンクに割れた入力・1 チャンクに 2 行ある入力・末尾に改行の無い入力・UTF-8 の 1 文字がチャンクの境で割れた入力を正しく読む。HTTP が 4xx のとき、`streamNewSideQuestion` は `ApiError`（`code` つき）を投げる。
- [ ] **Step 2: 失敗を確かめる**（`npm run test -- side-questions`）
- [ ] **Step 3: 実装する**。トークンの付け方とエラーの読み方は `lib/api.ts` の `postSpeech` に合わせる。CSP の `connect-src` は今の API と同じ接続先なので変えない。
- [ ] **Step 4: テストを通す**
- [ ] **Step 5: Commit**（`feat(explore): add side question client api`）

---

### Task 7: 選択と箇所の対応

**Files:**
- Create: `client/lib/text-anchor.ts`
- Test: `client/__tests__/lib/text-anchor.test.ts`

**Interfaces:**
- Produces:
  - `anchorFromRange(root: HTMLElement, range: Range): { quote: string; occurrence: number } | null`
  - `rangeFromAnchor(root: HTMLElement, quote: string, occurrence: number): Range | null`

**規則:**
- `quote` は選択の文字列の前後の空白を除いたもの。空・300 字超は `null`。
- 選択の始点と終点が、同じブロック要素（`p`・`li`・`h1`〜`h6`・`td`・`th`・`blockquote` の直下の文）の中に無ければ `null`。
- 始点か終点が `pre`・`.katex`・mermaid の図の中にあれば `null`。インラインの `code`・`strong`・`em`・`a` はまたいでよい。
- `occurrence` は、`root` の中で数える対象の文字（上の除外を除いた text node を文書順につないだもの）のうち、選択の始点より前に `quote` が現れた回数。
- `rangeFromAnchor` は同じつなぎ方で `occurrence` 番目の `quote` を探し、text node をまたぐ `Range` を返す。無ければ `null`。

- [ ] **Step 1: 失敗するテストを書く**（jsdom。DOM を組み、`Range` を作って渡す）
  - `returns quote and occurrence 0 for the first match`
  - `counts earlier matches: second "索引" has occurrence 1`、続けて `rangeFromAnchor` がその 2 番目の範囲を返す（往復して同じ文字列・同じ位置になる）
  - `selection across <strong> and <code> inside one paragraph round-trips`
  - `returns null across two paragraphs`
  - `returns null inside <pre>` と `.katex`
  - `returns null over 300 chars`、`returns null for whitespace only`
  - `rangeFromAnchor returns null when the text is gone`
- [ ] **Step 2: 失敗を確かめる** → **Step 3: 実装する** → **Step 4: 通す**（`npm run test -- text-anchor`）
- [ ] **Step 5: Commit**（`feat(explore): map text selections to stored anchors`）

---

### Task 8: 開閉と下書きの状態

**Files:**
- Create: `client/lib/side-question-tree.ts`、`client/hooks/use-side-questions.ts`
- Test: `client/__tests__/lib/side-question-tree.test.ts`、`client/__tests__/hooks/use-side-questions.test.tsx`

**Interfaces:**
- Consumes: Task 6 の型と API。
- Produces（純粋な関数）:
  - `interface SideDraft { tempId: string; parentId: string | null; anchor: SideAnchor; quote: string; occurrence: number; depth: number }`
  - `pathTo(threads: SideQuestion[], id: string): string[]`（自分と祖先）
  - `openOnly(threads, id): Set<string>`（自分と祖先だけを開く）
  - `closeWithDescendants(threads, open: Set<string>, id): Set<string>`
  - `childrenOf(threads, parentId: string, answerMessageId?: string): SideQuestion[]`
  - `topLevelInOrder(threads, messageOrder: string[]): SideQuestion[]`（本筋の応答の順 → 同じ応答の中は `occurrence` と作った順）
- Produces（フック）: `useSideQuestions(sessionId: string | null, enabled: boolean)` が返すもの:
  `threads`、`draft: SideDraft | null`、`open: Set<string>`、`streaming: { sideQuestionId: string; text: string } | null`、`error: { id: string; detail: string; content: string } | null`、`startDraft(draft)`、`send(id: string, content: string)`、`toggle(id)`、`openThread(id)`、`foldAll()`、`removeByAnchorMessage(messageId)`

**振る舞い:**
- `sessionId` が入ったとき（開始・再開）に `fetchSideQuestions` で読む。開閉は覚えず、全部畳んだ状態にする。
- `startDraft` は下書きを 1 つだけ持ち、それを開く。ほかを開く・畳むと、下書きは捨てる。
- `send`: 下書きなら `streamNewSideQuestion`、そうでなければ `streamSideFollowUp`。`started` で下書きを本物に置き換え、`chunk` を `streaming.text` に足し、`end` で回答を確定する。
- `streaming` がある間、`send` は何もしない（同時に 1 つ）。
- `error` のイベント・HTTP のエラーでは、送ったユーザーのメッセージを画面から外し、`error` に本文（`content`）を残す。入力欄に戻して「もう一度送る」で同じ本文を送れる。新規の質問で失敗したら、下書きに戻す。
- `removeByAnchorMessage`: 本筋の応答が取り消されたとき、その箇所の質問と子孫を画面から消す。

- [ ] **Step 1: 失敗するテストを書く**
  - tree: `openOnly keeps ancestors open`、`closeWithDescendants closes children too`、`topLevelInOrder sorts by message then occurrence`、`childrenOf filters by answer message`
  - hook（API は差し替える）: `loads threads folded on session start`、`draft is dropped when another thread opens`、`send on draft replaces it with the real thread on started`、`second send while streaming is ignored`、`error event restores content and removes the pending message`、`failed first send returns to draft`
- [ ] **Step 2: 失敗を確かめる** → **Step 3: 実装する** → **Step 4: 通す**
- [ ] **Step 5: Commit**（`feat(explore): manage side question state on the client`）

---

### Task 9: 画面（ボタン・右の欄・下線）

**Files:**
- Create: `client/components/chat/side-questions/selection-ask-button.tsx`、`side-question-panel.tsx`、`side-question-card.tsx`、`side-question-child.tsx`、`side-question-input.tsx`、`anchor-highlights.tsx`
- Modify: `client/app/(main)/learn/page.tsx`、`client/app/globals.css`（`::highlight()` の 2 つの規則だけ）、`client/lib/hints.ts`、`server/schemas/hint.py` とヒントの ID の一覧を持つマイグレーション
- Test: `client/__tests__/components/chat/side-questions/*.test.tsx`

**Interfaces:**
- Consumes: Task 6〜8、`ChatMessage.id`（Task 2）。

**見た目は見本（`2026-11-12-side-questions-mockup.html`）のとおりにする。** 文言も見本から: ボタン「ここについて質問」、見出し「質問」と件数、入力欄の placeholder「ここについて聞きたいこと」（最初）・「続けて聞く」（2 回目以降）、アイコンのボタンの `aria-label`「すべて畳む」「畳む」「送信」。

**決めてあること:**
- **出す条件**: `isExplore` かつ `md` 以上かつ `!useCoarsePointer()`。条件を満たさないとき、ボタン・右の欄・下線のどれも描かない（フックの `enabled` も false）。
- **応答の印**: 本筋の応答の入れ物に `data-message-id`、横の回答の入れ物に `data-side-message-id` を付ける。選択と下線は、この入れ物を `root` にする。
- **選べる応答**: `id` を持ち、ストリーム中でない assistant の応答と、確定した横の回答（深さ 3 の回答は除く）。
- **ボタン**: `mouseup` と `selectionchange` で `anchorFromRange` を呼び、`null` でなければ選択範囲の上・中央に出す。スクロール・選択の解除・Esc で消す。`mousedown` で選択を失わないよう `preventDefault` する。重なり順は `z-menu`。
- **下線**: `anchor-highlights.tsx` が、応答と横の質問が変わるたびに `rangeFromAnchor` で範囲を作り、`CSS.highlights` に 3 つの名前で入れる: `side-anchor`（全部）、`side-anchor-hover`（一覧で乗せているもの）、`side-anchor-open`（開いているもの）。`globals.css` の `::highlight(side-anchor)` は `text-decoration: underline` と下線の色、`-hover` は下線を濃く、`-open` は文字と下線を `var(--brand-text)`。`CSS.highlights` が無いブラウザでは何もしない（下線なしで右の欄だけ出る）。本筋のストリームで Markdown が描き直されても付き直ること。
- **下線のクリック**: 応答の入れ物の `click` で、選択が空のとき、押した位置が各範囲の `getClientRects()` のどれかに入っていれば、その質問を `openThread` する。乗せたときのカーソルも同じ判定で `pointer` にする。キーボードでは右の欄の行から開く（下線自体はフォーカスできない）。
- **右の欄**: `threads` も `draft` も無いときは描かない（本筋は今の幅のまま）。1 件目で出る。`xl` 以上は本筋の右に並べ（幅は見本と同じ約 25rem）、`md`〜`xl` 未満は本筋の上に重ねて出す（閉じるボタン付き。重なり順は `z-drawer`。閉じた後は、下線を押すとまた開く）。
- **枠と子**: 見本のとおり。いちばん上の質問ごとに枠 1 つ。畳んだ枠は「最初の質問」と「選んだ箇所」の 2 行と、子の質問の行。開いた枠は、選んだ箇所・会話・入力欄。子は、聞いた回答のすぐ下に、左の線と「↳」のアイコンで入る。開くと親は開いたまま。
- **会話の描画**: 横の回答は `Markdown`（`variant="chat"`）で描く。ストリーム中は `closeOpenBlocks` を本筋と同じに使う。
- **入力欄**: 1 行の `input`。Enter で送る。`isComposing` の間は送らない。空なら送信ボタンは押せない。`streaming` の間は全部の入力欄を止める。
- **エラー**: 枠の中に `error.detail` と「もう一度送る」。
- **取り消し**: 本筋の発言の取り消しで応答が消えたら、`removeByAnchorMessage` を呼ぶ（`cancel_last_message_success` と、編集して送り直す経路）。
- **ヒント**: `lib/hints.ts` に ID `explore_side_question` を足す。文面「AI の説明の文字を選ぶと、その箇所について横で質問できます」。explore で最初の応答が確定したときに、入力欄の上の `UsageHint` で出す。`md` 未満とタッチ端末では出さない。サーバーの `HintId` とマイグレーションの一覧にも足す。

- [ ] **Step 1: 失敗するテストを書く**
  - `panel is not rendered with no threads and no draft`
  - `collapsed card shows first question and quote, and child rows`
  - `open card shows quote, messages and input; child sits right after its answer`
  - `opening a child keeps the parent open`
  - `fold-all button is disabled when nothing is open and has aria-label "すべて畳む"`
  - `Enter during IME composition does not send`
  - `inputs are disabled while streaming`
  - `error shows detail and retry sends the same content`
  - `no text "往復" anywhere`
  - `learn page does not render the ask button or panel for a learning session`、`...on coarse pointer`
  - `ask button appears for a valid selection in an assistant message and not in a user message`
- [ ] **Step 2: 失敗を確かめる** → **Step 3: 実装する** → **Step 4: 通す**（`npm run test`、`npm run lint`、`npx tsc --noEmit`）
- [ ] **Step 5: 実物で確かめる**（`/run` の手順かローカルの開発サーバー。explore のセッションで）: 選ぶ → 質問 → 続けて質問 → 回答の中から子 → 再読み込みで下線と一覧が戻る → 同じ語の 2 回目を選んで 2 回目に下線 → 本筋で次の発言を送っても下線が残る → 本筋の発言を取り消すと、その応答の質問が消える → ライト・ダークの両方。Dark Reader は色を書き換えるので、色の確認は拡張を切って行う。
- [ ] **Step 6: Commit**（`feat(explore): ask about a selected passage in a side panel`）

---

### Task 10: 学習メモでの見せ方

**Files:**
- Modify: `client/lib/study-memos.ts`（`StudyMemoQuestion` に `quote?: string | null`、`parent_index?: number | null`、`from_side?: boolean`。`StudyMemoTerm` に `from_side?: boolean`。`groupStudyMemo`）、`client/components/study-memos/study-memo-aspect.tsx`、`study-memo-edit-form.tsx`
- Test: `client/__tests__/lib/study-memos.test.ts`、`client/__tests__/components/study-memos/*.test.tsx`

**決めてあること:**
- 疑問に `quote` があれば、質問の上に、選んだ箇所を薄い字で 1 行添える（左に線。右の欄の「選んだ箇所」と同じ見た目）。
- `parent_index` を持つ疑問は、親のすぐ下に、字下げと「↳」で並べる。親が同じ観点に無いとき（古いデータ・編集の後）は、ふつうの疑問として出す。
- `from_side` は画面に出さない（次の段階で使うデータ）。
- 編集フォームは今のまま（質問・回答・用語を直す、消す）。送る本文に足した項目は入れない。親を消すと子は残る、と分かるよう、消す確認の文は変えない。

- [ ] **Step 1: 失敗するテストを書く**: `question with quote renders the quote line`、`child question is rendered under its parent with indent`、`child whose parent is missing renders as a normal question`、`old memo without new fields renders as before`（スナップショットではなく、要素の有無で見る）
- [ ] **Step 2: 失敗を確かめる** → **Step 3: 実装する** → **Step 4: 通す**
- [ ] **Step 5: 実物で確かめる**: 横の質問をしたセッションを終え、学習メモに用語と疑問（選んだ箇所つき・子は親の下）が出る。編集で親を消しても子が残る。
- [ ] **Step 6: Commit**（`feat(study-memo): show questions asked on the side`）

---

### Task 11: 規約の更新と仕上げ

**Files:**
- Modify: `CLAUDE.md`（API の表に 3 ルート、主要テーブルに `side_questions`・`side_question_messages`、`LlmOperation` の注意に「横の質問は `turn` で数える」）
- Modify: `.claude/rules/server/graph.md`（横の質問はグラフの外・箇所は `dialogue_messages.id` に結び、取り消しはカスケードで消える・本筋のプロンプトと学習メモが同じテーブルを読む・学習メモの `quote` / `parent_index` / `from_side`）
- Modify: `.claude/rules/server/langfuse.md`（`traced_side_question()` と `digest-side-questions`）
- Modify: `.claude/rules/client/session.md`（出す条件・下線は `CSS.highlights`・右の欄は 1 件目で出る・`ChatMessage.id`）
- Modify: `.claude/rules/client/ui.md`（ヒント `explore_side_question`）

- [ ] **Step 1: 規約を書く**（コードから読めることは書かない。「なぜ」と制約だけ）
- [ ] **Step 2: 全部のチェックを通す**
  - `server/`: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`
  - `client/`: `npm run lint && npx tsc --noEmit && npm run test && npm run build`
- [ ] **Step 3: push の前に `git fetch origin` で main を見て、マイグレーションの `down_revision` を合わせる**
- [ ] **Step 4: Commit**（`docs: document side questions`）して PR を作る。本文に `Closes #828`、`## ドキュメントの更新`（上の 5 ファイルを 1 行ずつ）、確かめた手順（Task 9 の Step 5・Task 10 の Step 5）を書く。その前に `git rm --cached -r docs/superpowers` で資料の 3 ファイルをブランチから外してコミットする（`chore: drop planning documents from the branch`）。

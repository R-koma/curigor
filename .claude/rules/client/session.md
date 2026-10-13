---
paths:
  - "client/hooks/use-chat-websocket.ts"
  - "client/hooks/use-progress-*.ts"
  - "client/app/(main)/learn/**"
  - "client/app/(main)/review/**"
  - "client/components/chat/**"
  - "client/context/**"
  - "client/lib/progress.ts"
  - "client/lib/intake.ts"
  - "client/lib/topic-correction.ts"
  - "client/lib/session.ts"
  - "client/lib/active-session.ts"
  - "client/lib/trial.ts"
  - "client/lib/chat-markdown.ts"
  - "client/lib/explore.ts"
  - "client/lib/study-memos.ts"
---

# チャット画面（WebSocket・進捗・トピック・終了）

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。`useChatWebSocket`・学習と復習のページ・チャットの部品を触る前に関係すると分かっているときは先に読む。

- `use-chat-websocket.ts`: 接続ライフサイクル・メッセージ型振り分けを一元管理
- **WebSocket は想定外の切断で自動的につなぎ直す**（`useChatWebSocket`）: サーバーは放置で切らないが、uvicorn の ping タイムアウト（PC のスリープ・タブの凍結）、`fastapi dev` のリロード、デプロイで切れる。`learning` / `review` はトークンを取り直して `resume_session` を送り（間隔を空けて最大 5 回、タブの前面復帰と `online` では回数をリセットして即座に試す）、`synthesis` は再開できないのでエラーを出す。`end_session` の後にサーバーが閉じるのは正常な終了なので、`session_ended` を受けた後の切断では何もしない。サーバー側から接続を閉じる経路を足したら、それが再接続の対象になるか確かめること
- チャットのメッセージ本文は `Markdown` の `variant="chat"`（`remark-breaks` で単一改行を保持・`rehype-highlight` でコードをハイライト）で描画。ストリーミング中は `closeOpenCodeFence()` で未閉じフェンスを補ってから渡す（`notes`/`review` の `default`/`article` variant とは別系統）
- コピーは各メッセージ単位（`MessageCopyButton` が `msg.content` 全文をコピー）。未フェンスの貼り付けコードでも全文コピーできるよう、コードブロック単位ではなくメッセージ単位にしている
- 学習中の進捗表示は `LearningProgress.aspects`（観点名・中核か・到達段階）から観点ごとのパネルを描く。サーバーは核心の問いの本文と観点の `id` を送らない（AI がこれから問う内容を画面で先出ししないため。開発者ツールからも見せない）。段階の文言と通知の判定はクライアントの `lib/progress.ts` が持つ。聞き取りで得た目的・教材・今の理解は `LearningProgress.intake` で送り、観点マップの先頭に表示専用で出す（state の `learning_goal` / `learning_source` / `prior_knowledge` が源なので、自由文の返信から抽出した値も載る。3 項目とも空なら `None`）
- **トピック訂正の確認は聞き取りカードと同じ経路で出す**: サーバーの `topic_correction_question` を `ChatMessage.topicCorrectionCard` に載せ、最後のメッセージのときだけ `TopicCorrectionConfirm`（「はい、変更する」「いいえ」）を出す。回答は `sendMessage` の末尾の引数で `topic_correction_answer` として送り、吹き出しには `topicCorrectionAnswerText` の文を出す（`content` は LLM が読むので変えない）。再開時は `dialogue_messages.topic_correction_card` / `topic_correction_answer` から復元する。回答の発言は取り消せないのでやり直しボタンを出さない。確認が最後のメッセージのあいだは、聞き取りカードと同じく声の自動送信を止める（`choicePending`）。声で「はい」と言っても自由文として送られ、サーバーは「いいえ」扱いにするため
- **ヘッダーのトピック編集は `NavbarTopic` の `onEdit` で出す**: 鉛筆を出すのは接続中・応答の生成中でない・未終了・`progress.aspects` が空でないときだけ（復習の画面は `onEdit` を渡さない）。確定の前に `AlertDialog` で地図の作り直しと到達度のリセットを伝える。送った発言は `ChatMessage.topicEdit` で 1 行の表示（`TopicEditedNotice`）にし、やり直しボタンを出さない。ナビバーのトピック名は `assistant_message_end.topic` が届いてから変わる（送った時点では変えない）。サーバーが拒否したら `topic_edit_rejected` で 1 行の表示を消し、入力欄の下書きには触れない
- **セッションの終了ボタンは学習・復習とも `EndSessionButton`**（常にラベル付き。学習「ノートを作成」、復習「ノートを更新」）。応答の下の確認は `EndSessionConfirm`、ノートを作らずに終えたセッションの表示は `SessionEndedNotice`。確認が出ていても声の自動送信は止めない（声で再び終える意志を伝えると確定するため。聞き取りカード・トピック訂正の確認とは違う）。`endSession` は送れたかを返し、送れなかったときは終了ボタンを押し直せる
- **インプットセッション（`explore`）は `/learn` を流用する**: 開始画面の `StartModeToggle`（`?mode=explore` で最初から選ばれる）で `startExplore` を呼ぶ。インプットか否かは `sessionType`（`session_started` / `session_resumed` で決まる）を優先し、それまでは開始画面の選択（`exploreMode`）で見る。`progress` は送られないので、学習用のヒント・トピック編集・観点マップのパネルは出ない
- **全体像は `assistant_message_end.explore_overview` / `session_resumed.explore_overview` を `exploreOverview` に持つ**: 地図ができる前と他のセッションでは `null` が届くので、`null` で上書きせず直前の値を残す（`isExploreOverview` を通ったものだけ採用）。ヘッダーの `ExploreOverviewIndicator` と、最初の観点を選ぶ `ExploreAspectChoices`（まだ何も教わっていない間だけ、最後のアシスタントの発言の下に出す）が読む。観点の選択は専用のメッセージではなく自由文（`EXPLORE_START_TEXT` / `exploreAspectRequest`）を普通の `user_message` で送り、意図の判定はサーバーが行う
- **学習メモの完成は `note-status` の `study_memo_id` で知る**: `session_ended` の時点ではまだ無い。`generatedStudyMemo` が入ったら `/study-memos/{id}` へ移る。学ぶ内容が無いまま終えたとき（`note_skipped`）は作られず、`SessionEndedNotice` を出す
- **インプットの取り消しはサーバーが拒否する発言がある**: 全体像を作ったトピックの発言（全体像の失敗後に送り直した発言を含む）。教材カードへの回答は `IntakeAnsweredNotice` の表示でやり直しボタンが出ない。送り直したトピックはボタンが出るが、押すとエラーの通知になる

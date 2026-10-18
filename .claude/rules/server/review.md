---
paths:
  - "server/services/review_scheduler.py"
  - "server/services/review_focus.py"
  - "server/services/review_plan.py"
  - "server/graph/review_plan.py"
  - "server/graph/review_progress.py"
  - "server/graph/prompts/review_plan.py"
  - "server/repositories/review_plan_repository.py"
  - "server/api/routes/review_schedule.py"
  - "server/repositories/review_schedule_repository.py"
  - "server/graph/nodes/review_*.py"
  - "server/graph/nodes/_review_turn_analysis.py"
  - "server/graph/nodes/update_note_and_feedback.py"
  - "server/graph/prompts/review.py"
  - "server/graph/prompts/review_turn_analysis.py"
  - "client/app/(main)/review/**"
  - "client/components/review/**"
  - "client/components/dashboard/**"
---

# 復習スケジュールと復習セッション

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。復習の予定・回数・重点の観点・ダッシュボードの一覧を触る前に関係すると分かっているときは先に読む。

- **「今日」の暦日判定はユーザーTZで行う**: 復習スケジュールの時刻列は `TIMESTAMPTZ`（UTC 保持）。「今日復習を完了した件数」のような暦日集計を `last_reviewed_at::date = CURRENT_DATE` でやるとサーバーの稼働 TZ 次第で日付境界がずれる。`(last_reviewed_at AT TIME ZONE $tz)::date = (NOW() AT TIME ZONE $tz)::date` のようにユーザーTZ（`REVIEW_TIMEZONE`、既定 `Asia/Tokyo`）へ変換してから比較する。なお「期限到来済みか」の判定（`next_review_at <= NOW()`）は瞬間の前後比較なので TZ 非依存で問題ない。暦日に丸める集計だけが TZ 依存。
- **復習の開始で重点の観点を選べる**: `start_review.focus_aspect_ids`（省略可）で、復習で優先して聞く観点を選ぶ。開始画面の観点は初めは何も選ばず、空の `focus_aspect_ids` は「絞らない」。選んだ観点の点は質問プランの中で最優先になる。観点名は `services/review_focus.py` の `build_review_focus` が決め、`review_focus_aspects`（学習の `focus_aspects` とは別。区切りの提案の判定には使わない）に入れる。プランが無い復習（フォールバック）では従来どおり、最新の改善点を `prior_improvements` に入れ、選ばれなかった観点の改善点は入れない（観点に結びついていない改善点は常に入れる）。プランがあるときは `prior_improvements` を入れない（候補を使い切った後も）
- **復習完了はダッシュボードに残さず消す**: ダッシュボード（`GET /api/review-schedules`）は `next_review_at <= NOW()` かつ `status IN ('pending','overdue')` の未到来分だけを返す。実際の復習完了（review セッションの `update_note_and_feedback` → `_advance_review_schedule`）で `next_review_at` が将来へ進むと自動的に一覧から消える。フロントで「開いた＝復習済み」のような疑似状態を持って表示を残さない（次回到来まで非表示が正）。当日の進捗バーに必要な「当日完了件数」は一覧から消えるため `completed_today` として別途集計して返している
- **`review_count` は完了した復習の回数で、`calculate_next_review` には完了後の回数を渡す**: 学習直後は 0（翌日）、1 回目の復習の後は 1（3 日後）。学習（`generate_feedback`）はスケジュールを作るだけで回数に数えない。ダッシュボードの「N 回目」は次に行う復習なので `review_count + 1`
- **期限前の復習はスケジュールを動かさない**: 次の復習日が `REVIEW_TIMEZONE` の暦日で今日より後なら、`_advance_review_schedule` は回数・次の復習日・`last_reviewed_at` のどれも変えない（`is_early_review`）。まだ覚えているうちの復習を 1 回と数えると、定着していないのに間隔だけ伸びるため。フィードバックの履歴には残り、`completed_today` には数えない
- **質問プランはノートごとに 1 行（`review_plans`）で、学習の終了・復習の終了・本文の手での編集の後にバックグラウンドで作り直す**: ノートの本文を変える経路を足したら `schedule_review_plan` も呼ぶ。同じノートの生成はプロセス内のロックで直列にする
- **復習の開始は、ノート本文のハッシュの食い違いを見ずに手元のプランを使う**（待たせないため）。プランが無ければ同期で作り、`REVIEW_PLAN_SYNC_TIMEOUT_SECONDS` を超えたらプラン無しの今の復習にする
- **引き継ぎは直前の結果だけでなく、今のプランの引き継ぎで聞けなかったものも持ち越す**（説明できるまで残る）。重複は点の文言で除き（引き継いだ点は文言をそのまま保つ。`sanitize_plan_points` が強制する）、比べる相手は常に最新のフィードバックの `review_results`。時刻は比べない。プランの点の ID（`p1`…）はプランをまたいで安定しない
- **直前の結果で説明できた点（`explained` / `explained_with_hint`）は「前回説明できた要点」としてプランのプロンプトに渡し、`covered` の確かめ直し（1〜2 件・別の角度）にしか使わせない**: 復習は観点マップの `coverage` を更新しないので、渡さないと partial・uncovered の観点として毎回 `aspect_gap` に作り直される
- **終了の意志を示したターンは、いまの点を進めず、ヒントも使わず、`wrap_up_offered` も立てない**

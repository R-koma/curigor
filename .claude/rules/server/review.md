---
paths:
  - "server/services/review_scheduler.py"
  - "server/services/review_focus.py"
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
- **復習の開始で重点の観点を選べる**: `start_review.focus_aspect_ids`（省略可）で、最新のフィードバックの改善点のうち結びつく観点を絞る。絞り込みと重点の観点名は `services/review_focus.py` の `build_review_focus` が決め、改善点は `prior_improvements`、観点名は `review_focus_aspects`（学習の `focus_aspects` とは別。区切りの提案の判定には使わない）に入れてプロンプトへ注入する。省略・観点マップが無い・結びつきが無い行では、今までどおり最新の改善点を全部入れる。選ばれなかった観点の改善点は入れない（観点に結びついていない改善点は常に入れる）
- **復習完了はダッシュボードに残さず消す**: ダッシュボード（`GET /api/review-schedules`）は `next_review_at <= NOW()` かつ `status IN ('pending','overdue')` の未到来分だけを返す。実際の復習完了（review セッションの `update_note_and_feedback` → `_advance_review_schedule`）で `next_review_at` が将来へ進むと自動的に一覧から消える。フロントで「開いた＝復習済み」のような疑似状態を持って表示を残さない（次回到来まで非表示が正）。当日の進捗バーに必要な「当日完了件数」は一覧から消えるため `completed_today` として別途集計して返している
- **`review_count` は完了した復習の回数で、`calculate_next_review` には完了後の回数を渡す**: 学習直後は 0（翌日）、1 回目の復習の後は 1（3 日後）。学習（`generate_feedback`）はスケジュールを作るだけで回数に数えない。ダッシュボードの「N 回目」は次に行う復習なので `review_count + 1`
- **期限前の復習はスケジュールを動かさない**: 次の復習日が `REVIEW_TIMEZONE` の暦日で今日より後なら、`_advance_review_schedule` は回数・次の復習日・`last_reviewed_at` のどれも変えない（`is_early_review`）。まだ覚えているうちの復習を 1 回と数えると、定着していないのに間隔だけ伸びるため。フィードバックの履歴には残り、`completed_today` には数えない

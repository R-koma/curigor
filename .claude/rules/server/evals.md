---
paths:
  - "server/evals/**"
---

# eval（`server/evals/`）の運用

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。eval・capture・golden・judgeを触る前に関係すると分かっているときは先に読む。

## コマンド

```bash
uv run python -m evals.eval --mode scoring                    # 保存済み出力を採点（judge–人間一致を出す。既定は Haiku→Opus カスケード）
uv run python -m evals.eval --mode regression --runs 5        # input から再生成して採点（現行プロンプトの測定）
uv run python -m evals.eval --mode scoring --no-cascade        # カスケードを無効化し screen 単体で判定
uv run python -m evals.eval --mode scoring --strict            # 校正ゲート（TPR/TNR≥90%・正例レコード全件pass）不合格で exit 1
uv run python -m evals.eval --emit-instance <trace_id>        # golden の写しを正本 jsonl から生成
uv run python -m evals.eval --list-unannotated                 # 人間ラベル（pass）が無いレコードを一覧
uv run python -m evals.eval --mode regression --replay-mode pinned  # 保存済みの turn_decision を注入して応答生成だけ再実行
uv run python -m evals.eval --mode regression --route map --runs 3  # 経路で絞る（map / legacy / all。既定 all。校正ゲートは all で見る）
uv run python -m evals.eval --mode regression --emit-jsonl <path>  # regression の生成を正本へ追記
uv run python -m evals.eval --checkpoint-dir evals/reports/<name>  # 生成・採点の保存先を固定し、再開できるようにする（既定は自動生成）
uv run python -m evals.eval --mode scoring --no-judge-cache    # 保存済みの judge の判定を読まずに採点する（判定の揺れを見るとき）
uv run python -m evals.eval --mode scoring --judge-model claude-haiku-5-5 --judge-effort medium  # screen の effort を変える（effort を受け付けるモデルを --judge-model で指定したときだけ。判定キャッシュは effort ごとに分かれる）
uv run python -m evals.eval --mode regression --route map --trace <id> --no-cascade  # 指定した instance だけを安く確かめる（途中の確認用。--strict とは併用不可）

uv run python -m evals.tools.capture --list                   # 直近の learning セッション一覧
uv run python -m evals.tools.capture --latest --dry-run       # 直近セッションの生成レコードを表示（追記しない）
uv run python -m evals.tools.capture --session-id <uuid>      # 指定セッションを正本 jsonl へ追記（id 重複はスキップ）

uv run python -m evals.tools.annotate                         # annotate と golden 昇格の UI（http://127.0.0.1:8100。フィードバックの理解度は /feedback）

uv run python -m evals.tools.capture_feedback --list          # 直近のフィードバック一覧（captured / stale を表示）
uv run python -m evals.tools.capture_feedback --latest        # 直近のフィードバックを evals/datasets/feedback.jsonl へ追記（--session-id / --recent も可）
uv run python -m evals.feedback                               # 保存済みの理解度を人間のラベルと比べる（API を呼ばない）
uv run python -m evals.feedback --mode regression --runs 3    # 入力から理解度を作り直して採点し、揺れも出す（--trace <id> で絞れる）

uv run python -m evals.review_end --runs 3                    # 復習の「終えたい」の判定（`analyze_review_turn`）を手作りの evals/datasets/review_end.jsonl と比べる（LLM を呼ぶ。--trace <id> で絞れる）
```

> **Note:** jsonl の `input.graph_state` は**生成直前**の state（再実行の入力）で、`turn_decision` は
> **そのターンがプロンプトへ注入した値**（`response_mode` / `selected_aspect` / `error_summary` /
> merge 後の `covered_aspects`。`output` の直後・`input` の外）。`turn_analysis` はノードが読まずに
> 書くだけの値なので `input.graph_state.turn_analysis` は「前のターンの決定」であり、決定を注入して
> 再生成する用途（`--replay-mode pinned`）に使ってはいけない。
>
> **Note:** `input.graph_state.wrap_up_offered` が**無い**レコードは区切りの提案（`wrap_up`）を導入する前の
> capture であり、regression では提案済み扱いにして質問応答を再生する（完了基準を満たすレコードが
> 区切り応答に化け、質問応答を前提とした golden が壊れるため）。
> 区切り応答の golden は導入後に capture したレコードで別途作ること。
>
> **Note:** regression は **capture 由来のレコード（`meta.captured_by`）だけを再生成する**。手で転記した
> レコードは `conversation_history` が本番の `messages` と 1:1 になっておらず（トピック発話や
> `learning_start` の応答が欠けている）、`classify_user_intent` の判定とプロンプトの直近履歴が本番と
> 変わるため。スキップした理由は report に出る。`meta.route: "map"`（地図に沿った経路）のレコードも再生できる。
>
> `--route map|legacy|all`（既定 `all`）で経路を選び、ベースラインは経路ごとに取る（地図は `evals/baselines/map-v4-full.json`。v4 は費用を抑えるため `--no-cascade`（screen の judge だけ）で取った記録で、比べる実行も `--no-cascade` にそろえる。screen 単体は TNR 87%（2026-10-08 の scoring）で、主に `r1`・`r3` を誤って fail と判定するので、pass 率は実際より低く出る。v4 は地図の instance が 30 件で、v3（18 件・カスケードあり）とは共通の 18 件を screen の判定で比べる（confirm で決まった判定は screen では fail）。rubric の `r1` は v3 の後に文面を直した（#478）ので v3 と比べない。v1 は #375 前の旧プロンプトの記録）。
> checkpoint の実行条件は `route` と `map_prompt_fingerprint` も含むので、地図側のプロンプトを直すと既存の checkpoint では再開できない。
> レポート `meta.prompt_fingerprint` は旧経路の値のままなので、地図のベースラインどうしは `meta.map_prompt_fingerprint` で比べる。
>
> **Note:** トピック訂正の確認を出したターン（`turn_analysis.topic_correction.status == "asked"`）は LLM が応答を生成しないので capture の対象外。回答のターン（`accepted` / `declined` / `failed`）は `pinned` では再生できるが、回答の印を `conversation_history` が持たないため `full` では再生できない（`replay_blocker` が理由を出す）。
>
> **Note:** judge の判定は `evals/.judge_cache/`（gitignore）に、送った内容（モデル・判定の形式・プロンプト本文。基準・入力・応答を含む）の
> ハッシュで保存し、次の実行で同じ内容なら API を呼ばずに使う（`evals/judge_cache.py`）。基準を 1 つ直したときは、その基準の判定だけが
> 採点し直しになる。保存した判定を使うので、同じ入力に対する判定の揺れは現れない。揺れを見るとき・judge のモデルの中身が変わったときは
> `--no-judge-cache` で採点し直す。
>
> **Note:** jsonl の `source` と `failure_mode` / `first_failure` の値空間は `evals/taxonomy.py` が正本。
> 追加は `tests/unit/evals/test_dataset_invariants.py` が強制する（自由文字列だと表記ゆれで集計が割れる）。
>
> **Note:** capture は**セッション直後に実行する**。`meta`（model / prompt_version / prompt_fingerprint）は
> 実行時点のコードの値であり、セッション実施時点の値ではない。遡及エクスポートでずれた場合の一次資料は
> Langfuse の該当 trace（`sessionId = dialogue_session_id`）だが、Hobby プランは 30 日でデータアクセスが切れる。
>
> **Note:** eval は生成・採点を `--checkpoint-dir`（既定は `evals/reports/` 配下に自動生成）へ常に保存する。
> 途中で切れても、同じディレクトリを指定して再実行すれば保存済みの run は作り直さない。実行条件
> （プロンプト・judge・golden/rubric 本文などのハッシュ）が前回と違うディレクトリでは拒否される。
> 接続断・レート制限は自動で再試行するが、課金枯渇（クレジット・quota 切れ）は再試行しても直らないため
> 実行全体をその場で止める。保存済みの分はそのまま再開に使える。
>
> **Note:** プロンプト・golden・judge の基準を変える PR は、eval で確かめる項目を `evals/PENDING_VERIFICATION.md` に同じ差分で足す。
> 全件の regression・scoring はまとめて回し（地図のベースラインを取るときなど）、この一覧で照合する。issue ごとに `--trace` で回すのは、
> 後の作業がその修正を前提にする変更と、同じ箇所を複数の issue が直す変更だけ（運用はファイルの冒頭）。


## 注意事項

- **golden の deterministic assertion は `check_fingerprint`（`evals/checks.py` の実装の内容ハッシュ）を持たせる**: `check:` の名前だけでは golden から実装を辿れず、検出フレーズや判定ロジックを変えても record は無変更で通る。ずれたまま採点すると `human_verdicts` との不一致が judge の誤りとして現れ、**judge のせいでない failure を judge のせいだと誤診する**。値が動いたら criterion を読み直してから転記すること（実装が変わった記録であって、criterion がまだ実装を正しく説明しているかは人間しか判断できない）
- **eval の judge カスケードは screen の fail だけを confirm に回す**: エスカレーション条件（`should_escalate`）は `holds` ではなく polarity 適用後の verdict で判定する。screen（既定 Haiku）の FN（欠陥を pass と言う誤り）は confirm（既定 Opus）に届かないため最終判定に残る。scoring の校正ゲートは screen 単体の TPR も出すので、そこを見て「カスケードで救えない」誤りが無いか確認すること

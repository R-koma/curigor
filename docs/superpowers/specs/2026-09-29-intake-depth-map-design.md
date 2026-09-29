# 聞き取り＋深さの地図

## 背景・課題

学習対話（`learning_dialogue`）の質問生成は、観点の到達目標を「定義 → 具体例**または**動作原理」までとしている。この基準が緩いため、AI の問いが中核（なぜ必要か・どう動くか）ではなく周辺（日常の具体例）へ逸れやすい。実例：「システムコール」学習で、定義の直後に「ファイルを読み込むアプリを1つ挙げて」という問いが出て、深掘りが周辺へ流れた。

構造的な原因は2つ:

1. **トピックの「深さの地図」が無い**。観点はユーザー発言から後追いで抽出されるだけで、中核の問いをシステム側が持っていない。
2. **到達目標に「なぜ・仕組み」を必須にしていない**。具体例1つで到達扱いになり、浅い理解のまま区切りが提案されうる。

加えて、ユーザーの目的・前提知識を対話開始前に持たないため、地図があっても「何を中核とするか」「どこまで踏み込むか」を決める材料が無い。

## 目的・成功基準

- 学習開始時に、目的（何ができるようになりたいか）・出典（学習材料）・前提知識をチャットで聞き取る。
- 聞き取り結果をもとに、トピックの「深さの地図」（裏側データ、非表示）を生成し、以後の対話の観点選定・問いの方向づけに使う。
- 地図駆動の対話は、各観点で「なぜ・仕組み」まで届いて初めて到達とみなす。
- 既存セッション・既存 eval（capture・golden・regression）を壊さない。

## スコープ外

- セッションをまたぐロードマップ（書籍1冊などコース単位の管理）
- ユーザー単位の背景プロフィールの永続化
- RAG によるノート横断集約
- 復習セッション（`review_dialogue`）
- 地図駆動フローの新規 golden/eval データセット整備（今回のコードには手を入れるが、データセット追加は別作業）

## アーキテクチャ概要

`learning_dialogue` ノードを、state の `intake_complete` キーで3方向にルーティングする薄い入口に変える。グラフのエッジ・`GRAPH_VERSION` は変更しない。

```
learning_dialogue(state):
  intake_complete = state.get("intake_complete")   # 欠損 = 旧セッション（このキーを一度も書かれたことがない）
  ├─ None  → 旧経路（既存の prepare_turn/respond をそのまま呼ぶ。無変更）
  ├─ False → 聞き取り継続（新: graph/nodes/_intake.py）
  └─ True
       ├─ depth_map あり → 地図駆動の対話（新: graph/nodes/_map_dialogue.py）
       └─ depth_map 欠損 → 地図なしフォールバック（旧経路の prepare_turn/respond を自由記述カバレッジで実行）
```

**旧経路との切り分けが「値」ではなく「キーの有無」である理由**: `intake_complete` は新しい `learning_start` が最初のターンで必ず書く。デプロイ前に開始済みのセッションはこのキーを一度も書かれないため、`.get()` の欠損（`None`）は「新機能を経験していない」ことの確実な証拠になる。値を `False` 既定にすると、旧セッションと「聞き取り中の新セッション」を区別できない。

`evals/eval.py` は `graph.nodes.learning_dialogue` から `TurnPlan` / `prepare_turn` / `respond` / `learning_dialogue` を直接 import して regression・pinned replay に使う。これらのシグネチャ・挙動は無変更のまま維持する。旧 capture（`intake_complete` キーを持たない）は `to_state()` で state を組み立てても欠損のままなので、自動的に旧経路（`None`分岐）に入る。

## データフロー

```
learning_start（topic のみで開始）
  └─ intake_complete=False を書き、聞き取りの最初の問いを1つ返す
     （API から learning_goal が渡っていれば「目的」は聞かず、その分は省略した問いにする）

ユーザー返信 → learning_dialogue → intake_complete=False
  └─ _intake.py: 目的/出典/前提知識を構造化抽出し、既存の非空値を保ちつつ state へマージ
     ┌─ 揃った/ready_to_start/上限到達 → 完了処理（同一ノード呼び出し内で連鎖）:
     │    ① 深さの地図を生成（内部LLM呼び出し、INTERNAL_LLM_TAG）
     │    ② intake_complete=True, depth_map, map_covered=[] を書く
     │    ③ 地図駆動の最初の問いを生成して返す（ユーザーには1メッセージのみ届く）
     │    ※ 地図生成が失敗したら intake_complete=True かつ depth_map 欠損のまま
     │      次ターンへ進む（「地図なしフォールバック」。後述）
     └─ 未完了 → 不足項目だけを聞く次の問いを返す

以降のユーザー返信 → learning_dialogue → intake_complete=True
  ├─ depth_map あり → _map_dialogue.py の prepare_turn 相当 → respond 相当
  └─ depth_map 欠損（地図生成が失敗した回のフォールバック）→ 旧経路の prepare_turn/respond を
     自由記述カバレッジで実行（地図なし状態を引きずったまま継続する唯一のケース）
```

## 主要コンポーネント

### 1. 聞き取り（`graph/nodes/_intake.py` + `graph/prompts/intake.py`）

- 構造化出力 `IntakeExtraction`（`purpose: str | None` / `source: str | None` / `prior_knowledge: str | None` / `ready_to_start: bool`）。各ターン、直近のユーザー発言から抽出する。
- マージは非破壊: 既に値がある項目は、新しい抽出値が空でない場合のみ上書きする。
- 完了条件（いずれか）: 3項目とも値がある／`ready_to_start`／`intake_turns >= INTAKE_MAX_TURNS`（定数、既定 3）。
- プロンプトは「まだ不足している項目だけ」を自然な1つの問いにまとめる。全項目を機械的に列挙しない。
- `purpose` は既存の `learning_goal` state フィールドへ格納する（意味が同じため新設しない）。`source` / `prior_knowledge` は新規 state フィールド。
- `StartLearningMessage.learning_goal` が最初から渡っている場合、`learning_start` がそれを `learning_goal` に先に格納し、聞き取りの対象から「目的」を除外する（後方互換。既存 API 呼び出し元を壊さない）。
- `intake_turns` は新規 state フィールド。初期値 0（`learning_start` は最初の問いを出すだけで抽出を行わないため加算しない）。`_intake.py` がユーザー返信を処理するたびに +1 する。

### 2. 深さの地図（`graph/depth_map.py` + `graph/prompts/depth_map.py`）

- 生成は1回の構造化LLM呼び出し（`DepthMapGeneration`）。入力は topic + `learning_goal`（目的）+ `learning_source` + `prior_knowledge`（+ 後方互換として `focus_aspects` があれば「重視する観点」のヒントとして渡す）。
- 段階は `mentioned → defined → reasoned → applied` の4段階。**新設の型**とし、既存 `graph/coverage.py` の `ReachedDepth`（`mentioned/defined/exemplified/applied`）とは独立させる（旧経路のプロンプト・golden に一切影響させないため）。`exemplified`（具体例**または**動作原理）を `reasoned`（なぜ・仕組み）に置き換えるのが今回の核心の修正で、「具体例1つで到達」という浅い基準をなくす。
- 各観点 `DepthMapAspect`:
  - `id: str` — 安定スラッグ。以後はこの id で参照し、表記ゆれによる別観点扱いを防ぐ
  - `name: str` — 日本語の短い名詞句（プロンプト表示用）
  - `is_core: bool` — 中核観点は最大4件
  - `questions: dict[stage, str]` — 段階ごとの核心の問い（LLM が次の問いを組み立てる際の「向かうべき中身」。ユーザーへの文言そのものではない）
  - `applied` の核心の問いは `learning_goal`（目的）と結びつけて書く（例: 「`strace` で遅い処理の原因を切り分けられる」）
- 地図はユーザーに見せない。存在するのはプロンプト注入用の裏データのみ。

### 3. 地図駆動の対話（`graph/nodes/_map_dialogue.py`）

- 既存 `graph/nodes/_turn_analysis.py` と同型の事前分析だが、`observations` の観点は地図の `id` から選ぶ。
- 地図に無い話題が出た場合、事前分析は `new_aspect_proposal`（name + 簡潔な理由）を1件だけ出せる。採用されたら地図に `is_core=False` で追加し、以後は id で参照する。`id` は LLM に生成させず、コード側で `name` から決定的にスラッグ化する（地図生成時の `id` も同様）。追加観点はユーザー主導の topic pivot を尊重するためのものであり、区切り判定の分母には数えない。
- `map_covered: list[MapAspectProgress]`（`aspect_id` + `reached_stage`）。マージは既存 `graph/coverage.py` の `merge_coverage` と同じ「昇格のみ」ロジックを、型だけ新設のものに差し替えて流用する。
- 応答生成プロンプトは既存のモード A（誤りの訂正）/ B（展開）/ C（深掘り）構造をそのまま使う。選ばれた観点・目標段階に対応する地図の核心の問いを、モード本文の末尾に短い追加ブロックとして注入する（「この核心に向かって問いを組み立てる。日常的な具体例だけで終わらせない」）。ここが、問いが周辺へ逸れる問題への直接の対処。
- 区切り提案（wrap_up）: 地図の `is_core` 観点が**すべて `reasoned` 段階に到達**したら提案する。`graph/coverage.py` の `CoverageProgress` と同じ形を返す `depth_map_progress()` を `graph/depth_map.py` に新設する。
- `api/websocket/chat.py` の `_learning_progress()` は、`state["depth_map"]` の有無で `depth_map_progress()` と既存 `coverage_progress()` を呼び分ける。返り値の型（`CoverageProgress` 互換）が同じなので、`LearningProgress` スキーマ・`LearningProgressIndicator` コンポーネントは無変更。

## state 追加フィールド（`graph/state.py`、すべて `NotRequired`）

```python
intake_complete: NotRequired[bool]      # 欠損=旧セッション。毎ターン明示的に返す（wrap_up_offered と同じ流儀）
intake_turns: NotRequired[int]
learning_source: NotRequired[str]
prior_knowledge: NotRequired[str]
depth_map: NotRequired[DepthMapState]   # dict 化した DepthMap（DepthMapAspect のリスト等）
map_covered: NotRequired[list[MapAspectProgress]]
```

`TurnAnalysisRecord`（既存）に `selected_aspect_id: NotRequired[str]` を追加する。地図駆動ターンのみ埋める。`selected_aspect`（既存、表示用の名前）はそのまま残す。

## クライアント側の変更

- `client/app/(main)/learn/page.tsx`: 学習ゴール入力欄（`learningGoal` state・textarea・「学習ゴールを追加」トグルと関連アイコン）を削除。開始フォームは topic 入力のみになる。
- `client/hooks/use-chat-websocket.ts`: `StartLearningOptions.learning_goal` フィールド自体は残す（サーバーが後方互換で受け付け続けるため）。UI からは渡さなくなる。
- 進捗表示（`LearningProgressIndicator`）は無変更。

## エラーハンドリング

- 聞き取りの抽出LLM呼び出しが失敗した場合: 例外を飲み込み、その項目は空のまま次ターンへ持ち越す（既存 `_turn_analysis.py` の前例と同様）。
- 地図生成LLM呼び出しが失敗した場合: リトライはせず、`intake_complete=True` にしつつ `depth_map` は書かない。次ターンから「地図なしフォールバック」として、既存の自由記述カバレッジ（`covered_aspects` / `MODE_DIALOGUE` 自己判定）で対話を継続する。セッション内で地図生成を再試行しない（ユーザー体験上、聞き取りの繰り返しを避けるため）。
- `intake_turns` が上限に達しても3項目が揃わない場合: 揃った項目だけで地図生成を試み、欠けている項目はプロンプト上「未指定」として扱う（`format_learning_plan_fields` の既存パターンに合わせる）。

## テスト方針

- `server/tests/unit/graph/nodes/`:
  - 聞き取りの完了条件（3項目が揃う／`ready_to_start`／上限到達）
  - 非破壊マージ（既存値が新しい空抽出で消えない）
  - 地図生成失敗時のフォールバックへの移行
  - `intake_complete` 欠損時に旧経路（`prepare_turn`/`respond` 無変更呼び出し）へ分岐すること
  - API 起点で `learning_goal` が渡っている場合に聞き取り対象から除外されること
- `graph/depth_map.py`:
  - `merge`（昇格のみ）と `depth_map_progress`（中核観点が `reasoned` に揃うと `is_complete`）のユニットテスト。`graph/coverage.py` の既存テストと対になる形で書く
  - 新規観点の追加が `is_core=False` になり、`depth_map_progress` の分母に影響しないこと
- 既存 `evals` regression（`meta.captured_by` を持つ旧レコード）が無変更で通ることを確認する（新規ロジックが legacy パスに影響しないことの担保。テストコード変更は不要、CI の `server-test` で担保）。
- 地図駆動フローの golden/eval データセット追加は本スペックのスコープ外（別途 capture してから追加）。

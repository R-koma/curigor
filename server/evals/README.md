# evals — `generate_question` の振る舞い評価

`learning_dialogue`（`prepare_turn` → `respond`）が出す質問の振る舞いを、人間の判断基準（golden）に照らして LLM judge が採点し、その judge 自体が信頼できるかを人間ラベルとの一致で測る。

- 実行コマンドは `CLAUDE.md` の「開発コマンド」節。
- 対象は `generate_question`。フィードバックの理解度は別の仕組み（下の「フィードバックの理解度」節）で測る。review_dialogue・note は対象外
- Langfuse は store と viewer として使い、eval の engine にはしない。判断の根拠は `docs/adr/006-langfuse-eval-boundary.md`
- この文書は **golden を書く・judge を変える際に守る規約と、実測に基づく決定**だけを置く。
  コード（`taxonomy.py` / `eval.py`）とテスト（`tests/unit/evals/`）がここを参照するため git 管理下に置く

---

## 1. データの構成

- 正本は `datasets/generate_questions.jsonl`（1 行 = 1 ターン）。`evals/tools/capture.py` が実セッションから追記する
- golden（`datasets/golden/*.yaml`）は 1 ファイル = 1 `failure_mode`。型付き `assertions`
  （`type: deterministic | judge`、`criterion`、`polarity: must | must_not`）を 1 回だけ定義し、
  1 件以上の `instances`（正本の写し + 人間ラベル `pass` / assertion 別 `human_verdicts`）を持つ
- judge は 1 criterion・二値・`{reason, holds}`。`must` は `holds=true` で pass、`must_not` は `holds=true` で fail
- `human_verdicts` は保存済み `observed_output` へのラベルなので、judge–人間一致は scoring モードでのみ計算する

---

## 2. golden 側の規約

- **judge assertion は pass する instance と fail する instance を各 1 件以上持つ。** 満たせないうちは
  新しい judge assertion を追加しない。fail 側は synthetic でよい（`source: synthetic` を明示する）。
  片方向しか無い assertion は「judge がその向きを検出できるか」を一度も検証していない状態で、
  縮退した judge（常に `holds=true` を返すだけ）でも一致率が稼げてしまう。実測では、負例 2 件だけの
  時点で「常に true」の一致率が 6/9 = 67%、実際の judge は 80〜90% で、差は 1〜2 ラベルしかなかった。
  deterministic assertion は check 関数のユニットテストが両方向を担保するのでこの規則の対象外。
  強制は `tests/unit/evals/test_golden_assertion_coverage.py`。
- **assertion に適用前提があるなら `applies_when` に外出しし、条件を `criterion` に埋めない。**
  適用外の instance は `human_verdicts` に `na` を書く。条件を criterion に埋めると、前提を満たさない
  instance で「記述が当てはまらない」→ `must_not` が pass になり、適用外が合格として TN に計上される
  （FP/FN として現れないので混同行列を見ても異常が見えない）。`applies_when` が input だけの関数なら
  judge に聞かず静的に解決する（regression で N 回再生成しても適用可否は変わらないため）。
- **短絡すると答えが反転する独立条件を、1 criterion に並べない。** judge は先に満たした側だけで
  `holds` を決めて打ち切ることがある（`a1` の複合条件で実測）。判定の基準は連言の有無ではなく、
  **一部だけ読んで正しい答えに達するか**。OR や、主文が偽になる現れ方を言い換えただけの但し書きは
  短絡しても答えが変わらないので許容する。
- **但し書きを消して 1 文に畳むのは改善ではない。** 但し書きは主文の範囲を狭めており、消すと
  主文が広がってより多くを巻き込む。`a2` を「正しかった部分について AI がさらに説明を続けている」の
  1 文にしたところ、judge は「続けている」を**話を進める行為全般**と読み、質問（「さらに深い理解へ
  導く質問を提示している」）も訂正（「より正確な説明を続けている」）も該当と判定した。`a1` では
  主語が曖昧になり、Sonnet が「AI 自身が答えるべき質問ではないので判定対象が存在しない」と結論した。
  実測は Haiku 18/20・Sonnet 19→17/20・Opus 20/20 で、1 文版は明確に悪化した。
  守るべきは文の数ではなく、**主文だけを読んで正しい答えに達する形になっているか**。
- **criterion を精密にして judge が pass に転じたら、まず守備範囲の重複を疑う。**
  `a1` を「焦点の単一性」と「質問の具体性」に割った際、後者を精密にするほど judge は pass を返し、
  人間ラベルの fail と食い違った。調べると、その応答の欠陥（既出内容の再説明要求）は `a3` が既に
  拾っており、曖昧な criterion が `a3` の担当分を吸い込んで**二重計上**していただけだった
  （後者は削除し `a1` に戻した）。**ラベルに合わせて文面を調整する前に、その欠陥を別の assertion が
  既に検出していないか確認する。** n=1 のラベルに文面を寄せ続けるのは criterion の過剰適合で、
  一致率は上がるが検出しているものは増えない。
- **criterion は複数の judge モデルで同じ判定になって初めて「書けている」と言える。**
  モデル間で判定が割れたら、能力差ではなく **criterion の曖昧さ**を疑う。実測では `a1` の
  「回答可能になっている」の閾値（完全性か中核か）が書かれておらず、Haiku=fail / Sonnet=pass /
  Opus=fail と**非単調に**割れた。能力差なら最小のモデルが落ちるはずで、小と大が一致して
  中だけ外れるのは解釈が分かれている証拠。逆に全モデルが一致するなら、それは criterion どおりの
  判定であり、直すべきは criterion の側（`a2` で実測）。切り替えは `--judge-model`。
- **assertion に instance 固有の事実を書かない。** criterion は failure_mode 全体の契約なので、
  特定の trace にしか当てはまらない固有名詞や誤りの中身を埋めると、2 件目の instance を足した
  瞬間に使えなくなる。instance 固有の事実は `rationale` に置く。
  `a4` は「（「OSから独立したメモリ空間」——正しくは…）」と誤りの正解を criterion に埋めていたが、
  外しても judge は自力で不正確な箇所を特定できた（**judge に答えを渡す必要は無かった**）。
- **failure_mode をまたぐ assertion は `datasets/rubric/` に置き、golden 側に複製しない。**
  id は `r` 始まりにしてファイル内 id（`a1`, `a2`, ...）と衝突させない。合流は
  `evals.rubric.merge_assertions` が `record["assertions"]` の一点で行い、由来を `scope` に残す。
  複製を放置すると片方だけ直したときに静かに食い違う（実際「一般化した促し」は 3 ファイルに
  同じ文面で存在し、`uncorrected_misconception` だけ id が `a3` とずれていた）。
  rubric の assertion は全 instance に適用されるので、**両方向カバレッジは golden 全体で満たせばよい**
  （failure_mode ごとに要求すると、その観点が出ない失敗モードで必ず落ちる）。
- **AI が「学習者からは出てこない知識」を補完することは許す（2026-09-23 決定）。** `r1` が禁じるのは
  **言い直し**（ユーザーが自分の言葉で述べた内容の再説明・補強）だけで、ユーザーがまだ述べていない
  内容を新たに渡すことは含まない。名前を挙げただけの観点についても、その中身を説明することは
  「新たに渡す」側に入る。禁じる理由は学習者のターンを消費して「AI が説明し自分は聞く」形を
  強化することなので、単独では到達できない枠組みを短く渡して次の問いを開くのはこれに当たらない。
  golden の正例（`0f43b9c0__t8-exemplar` など）は以前から補完を行っており、それが通っていたのは
  「誤りを訂正するため」という除外条項に当たるからだった。訂正を伴わない補完に通り道が無かったのを
  この決定で開けた。
- **補完を許す代わりに、自己回答（`r3`）を rubric へ置く。** 補完を無害にしている条件は
  「直後の問いの答えを渡していないこと」で、これは `self_answered_question` 固有ではなく
  全モードで起きる。`r1` だけを緩めて `r3` を 1 ファイルに残すと、他ファイルの instance で
  「補完した上でその答えを聞く」応答を検出する assertion が無くなる（実際 `r1` が fail の 6 件のうち
  4 件がその状態だった）。`self_answered_question` の `a1` を `r3` として rubric へ移し、`a1` は欠番にした。
- **golden から assertion を抜いたら、残った id は詰めない。** 欠番のまま残す。詰めると既存の
  `human_verdicts` が別の assertion を指すようになり、付け直しの履歴を辿れなくなる。
- **`input` / `observed_output` / `meta` / `source` は正本 jsonl からの写しで、手で書かない。**
  `evals.golden_yaml.dump_copy_block` で生成する。`tests/unit/evals/test_golden_copy_matches_source.py`
  がバイト一致を保証し、落ちたら写しを再生成する一択。
- **golden の YAML は読み込んで書き直さない。** `>` の折り返しとコメントが落ち、assertion 定義と
  他の instance が壊れる。`evals.tools.annotate` が書けるのは、`instances:` の末尾への追記
  （昇格）と、1 つの instance の `human_verdicts` ブロックの差し替え（付け直し）だけ。
  criterion・rationale・assertion の変更はエディタで行う。**criterion は判定の基準そのもの**なので、
  摩擦を残して git diff と PR レビューを通す。
- **`pass: false` の instance は `fail` の verdict を 1 つ以上持つ。** どの assertion も fail にならない
  負例は、その失敗を検出する契約がどこにも無いということなので、別の failure_mode を選ぶか
  assertion を先に足す。`na` を付けてよいのは `applies_when` を持つ assertion だけ。
- **annotate で書き換えてよいのは `pass` / `first_failure` / `note` / `annotated_at` の 4 つだけ。**
  `input` / `output` / `meta` / `turn_decision` は golden の写しとバイト比較されるので触らない。
  UI（`evals.tools.annotate`）もこの 4 つしか書かない。
- **annotate は地図のレコード（`meta.route: "map"`）に、地図の到達度を出す。** 観点ごとの直前の段階と
  このターン後の段階、選ばれた観点・応答モード・誤りの判定、プロンプトに入った核心の問い
  （`evals/tools/annotate/map_view.py`）。画面は開発者用なので、核心の問いも出してよい。
  表示は読み取りだけで、`turn_decision` は書き換えない。旧経路のレコード（`route` なし）の表示は変わらない。
- **jsonl を手で書いて増やさない。** capture が潰すべき作業で、推測フィールドが再混入する。
  増やしたいなら実セッションを回して溜める。
- **`observed_output` は撮り直さない。** judge 校正用の人間ラベルが全部無効になる。
- **failure_mode は golden ファイルを持たなくてよい。** instance が両方向揃うまでは `taxonomy.py` の
  ラベルとしてだけ使い、検出は rubric や他モードの assertion に委ねる。ファイルを先に作ると
  「両方向の instance が揃うまで judge assertion を足さない」規約を最初から破ることになる。
  `overexplained_correct_content` がこの状態で、検出は rubric の `r1` と `r3` が担っている。
- **`failure_mode` / `first_failure` の値空間は `taxonomy.py` が正本。** 網羅的な taxonomy を今作らないのは
  意図的で、error analysis が ~100 trace で saturation してから。追加は PR レビューに通す。

---

## 3. judge は Haiku→Opus の 2 段カスケード（2026-09-05 決定）

**採用: screen（既定 Haiku 4.5）で全件判定し、screen が fail と言った judge assertion だけ
confirm（既定 Opus 5）に回す。** `--judge-model` / `--judge-effort` が screen、`--confirm-judge-model` が confirm、
`--no-cascade` で従来の単一 judge に戻せる。

**screen を Haiku 5.5 に替えない（2026-10-10 に scoring 全件で実測）。** effort `low` では screen の TPR が
96.6% → 87.9%（FN 2 → 7）に落ち、final の校正ゲートが不合格になった。誤った fail は 34 → 13 件に減り費用も
およそ半分になるが、screen の FN はカスケードで救えない。`medium` でも FN は 7 件のまま、キャッシュ無しの
再実行では FN 12 件（判定の 13/207 件が反転）。判定の理由を読むと、Haiku 5.5 は基準を文字どおり・好意的に読み、
境界の事例（問いのねじれ・「これら」でまとめた複数の側面・趣旨が同じ問い直し）を pass にする。Haiku 4.5 は
理由と判定が食い違ったまま fail に倒すことがあり、それが screen の役割に合っている。

Haiku 5.5 などを `--judge-model` で使うときの注意: temperature を受け付けない（既定以外は 400）ので判定は
決定的でなく、安全のための分類器が判定を拒否することがある（`JudgeRefused`。再試行しない）。
`--judge-effort` は effort を受け付けるモデルにだけ付けられ、judge の名前（`judge_model_name`）は effort を含み
（`claude-haiku-5-5@low`）、判定キャッシュと checkpoint は effort ごとに分かれる。

### 根拠（実測）

Haiku の誤りは全て FP（FN=0、TNR=85%）、Opus は FP=0（TNR=100%）。つまり Haiku が pass と
言ったものは信用でき、fail と言ったものだけ疑わしい。この非対称性がカスケードを成立させる。
`a2` の FP はいずれも「訂正のための記述」を「言い直し・補強」と読む誤りで、4 通りの文面
（下表）で再現するため文面調整では直らない（Haiku の弁別能力の限界）。

| criterion の形 | Haiku 4.5 | Sonnet 5 | Opus 5 |
|---|---|---|---|
| 現行（但し書きあり） | 18/20 | 19/20 | 20/20 |
| 1 文に畳んだ版 | 18/20 | 17/20 | 20/20 |
| 定義または具体例を新たに提示している | FP=2 | — | — |
| 正しく述べた内容を言い直し・補強して解説している | FP=2 | — | — |
| 正しかった部分についてさらに説明を続けている | FP=2 | — | 20/20 |

### 合格条件（総合一致率から方向別へ変更）

総合一致率だけでは「良いものを fail と言う」偏りが 90% の下に隠れる。`calibration_gate()` が
`TPR ≥ 90% かつ TNR ≥ 90%` に加えて **正例レコードが judge 集約で全件 pass** を要求する
（`stage="final"` のときのみ）。`--strict` を付けると scoring モードで final ゲート不合格時に
exit code 1 になる。

### 限界（カスケードが救わないもの）

**screen の FN（欠陥を pass と言う誤り）は confirm に届かない。** confirm はエスカレーション
条件（`should_escalate`: polarity 適用後の verdict が fail）を満たしたときだけ動くため、screen が
pass と誤判定した場合はそのまま最終判定になる。最終判定の TPR ≈ screen の TPR、TNR ≈ confirm の
TNR。scoring の校正ゲートは `stage="screen"` の TPR も出すので、そこが閾値を割ったら
「カスケードでは救えない」旨が failures に出る。

### 決めた際に確認した点

- **判定器を明示しない一致率は意味を持たない。** 同じ golden・同じ criterion でも、judge モデルを
  変えると一致率が変わる（`--judge-model` / `--confirm-judge-model` で切り替え可能）。report の
  `meta.judge`（screen/confirm）に必ず併記する
- `a2` の criterion 自体は変更していない（文面調整では直らないことを確認済みのため）
- judge は temperature 0 でも判定が揺れる（同一入力で `a2` が fail/fail/pass/pass と反転した実測あり）。
  **1〜2 ラベルの差を読まない**
- 20/20・final 校正ゲート PASS は golden 4 instance・20 ラベルでの値。judge の信頼性・失敗モード率の
  統計的意味は 20〜30 件に届くまで保留（残課題と手順は `docs/note/`）

## 訂正・補足後の理解確認（2026-09-25）

AI が一般則・定義・必要な前提を教えることは許可する。r3 は、AI が学習者に出した
具体的な問いへの結論・適用結果を、その応答で先に提示していないかを判定する。
説明の抜き出しや復唱を求める質問は不合格だが、新しい条件への適用結果が未提示なら、
同じ用語を使ったり教えた一般則から答えを導けたりしても、それだけでは不合格にしない。
訂正ケースの a2 は「訂正して、その知識を使う問いで理解を確認したか」を担当し、
答えの先出しの有無は r3 に任せる。

境界例は `datasets/calibration/r3_application.yaml` に保存する。期待値は承認された方針に基づく
Codex 作成の評価用データであり、人間が確認済みの golden ラベルとは区別する。
各カテゴリで合格・不合格の両方向を、Haiku と Opus でそれぞれ検証する。
既存 golden の r3・a2 は全16入力・保存出力を確認し、今回の明確化ではラベルを変更していない。

評価基準を変えた比較は、同じ保存済み出力の再採点と、基準を固定した生成プロンプトの比較に分ける。
旧レポート・旧ラベルを上書きしない。実験ごとに基準本文・ラベル・ハッシュを保存する。
regression レポートは各runの `covered_aspects` も保存する。古いレポートにはこの値がないため、
分析結果だけが一致しても当時のプロンプトを完全再現したとは扱わない。
地図に沿った経路の run は `map_covered` / `depth_map` も保存し、観点の run 間一致（`coverage_stability`）は `aspect_id` で比べる。

## 応答の反復・「わからない」への応答・学習者の質問（2026-10-05）

地図に沿った経路の応答品質を直す前に、次の 3 つを失敗の型として測る（`taxonomy.py`）。

- `repetitive_phrasing`: 直前までの応答と同じ書き出し・定型句を繰り返す
- `ignored_learner_question`: 学習者の質問・説明の依頼に答えないまま問いを返す
- `monotonous_unknown_support`: 「わからない」が続いたときに、同じ支援の仕方か同じ問いの言い換えを繰り返す

あわせて「学習者がまだ口にしていない概念を、知っている前提で問う」問題は、新しい型を作らず
`preempted_learner_explanation` に入れる。

書き出しの反復は、ターンをまたいで比べる deterministic check `repeats_previous_opening` で見る。
この check は応答だけでなく `conversation_history` を受け取る。比べる範囲は、直近 3 件の AI 応答の
書き出し（最初の読点・句点まで）で、4 文字未満の書き出し（「では」など）は比べない。

- rubric（全 instance）には入れず、`repetitive_phrasing` の golden に置く。
  rubric に入れると既存の全 instance に人間ラベルを付け直す必要があり、check の判定を写したラベルでは一致率が自明になる
- 3 つの型の golden は、実セッションを capture して pass・fail の両方向の instance がそろってから作る（2 節の規約）。
  それまでは annotate の `first_failure` として付けるだけにする
- 雑談など、学習の説明でも質問でもない発言への扱いは、capture したデータで頻度を見てから決める

### 失敗の型の追加と手書きの理想の応答（2026-10-06）

「Linuxのしくみ」の annotate（#432）の turn 8・10 を読み直し、既存の型に当てはまらない失敗を 2 つの型にした。

- `assumed_unmentioned_concept`: 答えるのに、学習者がまだ口にしていない専門的な概念の知識が要る問いを、説明なしに出す。
  turn 8 は、メモリにも仮想アドレスにも触れていない学習者に、仮想アドレスと物理メモリの対応を問い、次のターンで「わかりません」になった。
  日常の経験で答えられる問い（turn 18 のファイル操作）は含めない。実際に学習者が答えられたため。
  `preempted_learner_explanation`（AI が説明を先に述べる）とは別。こちらは問いの前提が学習者の知識を超えている。
- `insufficient_unknown_scaffold`: 「わからない」のあとに説明を足しても、次の問いが漠然としていて足場を渡さない。
  turn 10 は、日常の利用場面を 1 つ挙げて、と求めるだけだった。`undirected_followup`（定型句で促す）とは別で、
  `monotonous_unknown_support`（同じ支援を繰り返す）とも別（こちらは初回でも起こる）。

turn 8 は `abrupt_topic_transition` も該当するが、`first_failure` は 1 つなので、前提の問題を優先してメモに併記した。

手書きの理想の応答（`source: handwritten`、`pass: true`）を、同じ実セッションの turn 10・12・14・16・18・26・28 に 1 件ずつ足した（id は `-exemplar`）。
入力は実レコードのものをそのまま使うので、annotate で実際の応答と見比べられる。
`meta.captured_by` が無いため regression では再生されない（2 節の規約どおり、golden の pass 側の正例として使う）。
どれも `contains_generic_prompt_phrase` と `repeats_previous_opening` には該当しないことを確認済み。
LLM judge（r1・r3）には通していない。golden に昇格するときに採点して、判定のずれを確認すること。
- turn 26・28 の正例は、実在する操作（「ノートを作成」ボタン）へ案内する。AI はセッションを終了できず、ノートの作成は #430 で扱う

### 対話の支援の失敗の型を golden にする（2026-10-06）

regression は golden の instance だけを再生する。annotate でラベルを付けただけのレコードは採点されない。
「Linuxのしくみ」（#432）のレコードと手書きの正例（#454）を、次の 7 つの golden（`status: draft`）に昇格する。

| golden | fail（実レコード） | pass |
| --- | --- | --- |
| `insufficient_unknown_scaffold` | t10 | t10-exemplar |
| `premature_wrap_up` | t12 | t12-exemplar |
| `repeated_answered_question` | t16・t24 | t16-exemplar |
| `assumed_unmentioned_concept` | t8 | t6 |
| `abrupt_topic_transition` | t18 | t20 |
| `ignored_session_end` | t26 | t26-exemplar |
| `note_request_answered_in_chat` | t28 | t28-exemplar |
| `self_answered_question`（既存） | t14・t22 | t14-exemplar |

- 1 つのレコードは 1 つの golden にしか昇格できない（`validate_promotion`）。そのため pass 例は golden ごとに別のレコードを当てた
- 実レコード（fail）は regression で作り直して採点する。手書きの正例は `captured_by` が無いので regression では再生されず、
  `--mode scoring --strict` で judge が pass を pass と判定できるかの確認に使う
- 昇格がそろったら、`status` を `active` にする。`draft` のままでは regression に読まれない（2026-10-07 に全件昇格し、`active` にした）
- この 18 件の `human_verdicts` と rationale は Claude が下書きし、R-koma が全件を確認して採用した。rationale の先頭の【下書きは Claude、確認は R-koma】はその来歴。
  下書きを先に見たラベルなので、judge との一致率は、白紙から付けたラベルより高く出る可能性がある
- `repetitive_phrasing`（`repeats_previous_opening`）は golden にしていない。該当するレコード（t12・t16・t22）が
  別の golden に入るためで、扱いは改めて決める

### 校正ゲートの不合格と修正（2026-10-07）

上の golden を入れて `--mode scoring --strict` を実行すると、final の TPR は 90%・TNR は 99% だったが、正例レコードが 18 件中 17 件しか
judge で pass にならず、ゲートは不合格だった。ずれた 3 件を次のとおり直した（残り 2 件は以前からある r1 のずれで、今回とは無関係）。

- `t16-exemplar`（r3: judge fail / 人 pass）: 手書きの正例が「表に載っていない」と書いたため、問いの答えが前提の否定で自明になっていた。
  judge が正しいと判断し、答えが前提から導けない問いに書き直した
- `t18`（`abrupt_topic_transition` の a1: judge pass / 人 fail）: judge は「では、」を話題を移す言葉と読んだ。基準の文面どおりの読みなので、
  「接続詞だけで移った場合は、つながりを示したことにならない」を基準に足した
- `t24`（`repeated_answered_question` の a1: judge pass / 人 fail）: 問いの答えの中心（新しいデータを置く場所を見つける・上書きしない）は、
  学習者がまだ述べていなかった。直前の回答と同じ答えを求める問い直しではないため、人のラベルを pass に変えた（annotate のラベルも同じ）

修正後にもう一度実行すると、final の TPR は 85% で不合格だった。新しく外れた 3 件は、どれも screen が fail と判定し、confirm が pass に覆していた。
confirm の理由が基準の読み違いによるものは、基準の文面を補った（golden のラベルは変えていない）。

- `t26`（`ignored_session_end` の a1）: confirm は、問いが以前の問いの繰り返しなので「新しい問い」ではないと読んだ。
  「新しい」を外し、言い直しや繰り返しも含むと書いた
- `t16`（`repeated_answered_question` の a1）: confirm は、問いの前に足した説明を理由に、別の側面を問うていると読んだ。
  問いの前に説明を足していても、問いが求める答えが直前の回答と同じなら該当すると書いた
- `t18`（`abrupt_topic_transition` の a1）: 前回の修正の後も外れた。confirm は、応答の前半の答えがつながりを示していると読んだ。
  前半で質問に答えていても、移った先の問いとのつながりを示していなければ該当すると書いた
- `2026-07-14-os-process__t1`（共通の r3）: 前の 2 回は judge と人がそろっていた。判定の揺れとみて、共通の基準は変えていない

正例の判定が 39 件のとき、TPR 90% を満たすのは外れが 3 件までで、以前からの r1 の 2 件を除くと余裕は 1 件しかない。
基準の境界にある例は、実行ごとに結果が変わりうる。

#470 の後の実行でゲートは合格した（final の TPR 92%）。残った 3 件のずれは前から続いていたので、ラベルと基準を読み直した。

- `2026-07-08-ddia-ch1-perf__t3` と `2026-09-21-6c938091__t4`（共通の r1）: どちらの応答も、ユーザーの定義の言い直しと、新しい例や手段の
  解説を含む。judge は新しい部分だけを見て pass にしていた。ラベルは正しいので、r1 に「新しい内容が含まれていても、言い直しや補強の部分が
  あれば該当する」を足した。t4 の rationale は r1 の根拠に新しい手段を挙げていたので、言い直しの部分に絞った
- `2026-07-14-os-process__t1`（共通の r3）: 問いが求める「管理方法」は応答に書かれておらず、「さらに詳しく」は説明の抜き出しではない。
  人のラベルを pass に変えた。この応答の欠点は r2・a3・a4 が捉えている

r1 は共通の基準なので、文面を変えた後は全レコードの判定を scoring で確かめる。

その後の実行（#477 の後）で、r1 の FP が 4 件に増え、正例レコード 2 件が pass にならずゲートは不合格だった。judge は、学習者の
言葉を 1 文で引いて次へつなぐ受け止め（例: 「HTTPのメッセージには、ヘッダーや本文があります」）まで言い直しと数えていた。
t3・t4 は定義を何文もかけて説明し直していた例なので、足した一文を「説明し直している部分」に絞り、1 文で引いてつなぐだけのものは
短い受け止めの復唱にあたると明記した。これでも揺れるなら、文面の調整はやめ、一文を外すか、境界の例を golden に足す。

### 問いの分かりにくさと書き出しの反復を golden にする（2026-10-07）

「わからない」を 3 回続け、質問・一部だけの「わからない」・終了の意思を含めたセッション（`2026-10-07-6eab2de3`、HTTP のしくみ）を
capture し、次を足した。

- `unclear_question`（新設）: 問いが日本語として崩れている、または回りくどく、一度読んだだけでは何を答えればよいかが分からない。
  崩れた例が t12（選ぶ候補を示さずに「どちらか」と聞く）、回りくどい例が t18（「〜と比べて、〜では何が変わるか」）。
  t18 は答えを直前に述べてもいるが、それは全ターンに共通の r3 で採点されるので、こちらに入れた。長い問いや専門用語を含む問いは
  該当しない（`assumed_unmentioned_concept` と分けるため）
- `repetitive_phrasing`: `repeats_previous_opening` の決定的チェックだけで判定する。fail の例は t14（t10 と同じ書き出し）
- t14 の手書きの理想の応答は、3 回目の「わからない」で答えの中核を述べ、述べていない場面への適用を問う形にした。
  選択肢を変えて問い続けるより前に進めるため（PR-3 の 3 回目からの支援の設計に使う）

### 以前の学習に触れた発言を golden にする（2026-10-08）

関連する過去のノート（`related_notes`）を入れたセッション（`2026-10-07-f04cfbc9`、ロードバランサー）では、学習者が
自分から以前の学習に触れたのに、AI がつながりに何も言わずに次へ進んだ。これを `unlinked_prior_learning`（新設）として測る。

| 区分 | instance |
| --- | --- |
| fail | t12（「前にスケーリングを勉強したとき、いつ増やすかがわからないままだった」）・t24（「サーバー自体を強くする方法も勉強した」） |
| pass | t12-exemplar（手書き。ノートで分からないまま残っていた点と今の話のつながりを 1 文で示す） |

- `applies_when` は「学習者の直前の発言が以前の学習に触れている」。judge には関連ノートを渡さないので、
  判定は会話の中で学習者が触れた内容だけで決まる
- t12 は annotate で pass だったが、この型の fail に付け直した。t24 の `first_failure` は `premise_shifting_correction` のまま
- `human_verdicts` と rationale は Claude が下書きし、R-koma が確認して採用した（2026-10-08。rationale の先頭の【下書きは Claude、確認は R-koma】）
- 既存の golden は `related_notes` を持たないので、プロンプトの「以前の学習に触れたらつなげる」規則の効果はこの golden でしか測れない

### 前提の中で正しい説明を否定する訂正を golden にする（2026-10-08）

関連ノートの確認で回した 2 セッションで、学習者の前提の中では正しい説明を、AI が別の前提を持ち込んで否定した
（`premise_shifting_correction`。#505 で新設）。どちらも事前分析が `has_misconception` を立て、応答が訂正のモード（reinforce）に入っていた。
地図の事前分析（`map_turn_analysis.py`）の誤りの基準に、前提の中で成り立つ説明・一般的な比較を誤りにしないことと、
`error_summary` が「〜とは限らない」としか書けないなら誤りではないことを足した。

| 区分 | instance |
| --- | --- |
| fail | `2026-10-08-7f7c60c6__t16`（油絵具と比べて「水彩だとすぐ乾く」を、種類や環境の例外で「誤り」と断定） |
| pass | `2026-10-07-f04cfbc9__t22`（共有の場所に置く構成を前提にした説明を、その前提の中で受け止める）・`__t16-exemplar`（手書き） |

- もう 1 件の例（`2026-10-07-f04cfbc9__t24`）は `unlinked_prior_learning` の golden に入っているので、ここには入れていない（1 レコード 1 golden）
- 事前分析の基準を変えたので、反対側の失敗（`uncorrected_misconception`：本当の誤りを訂正しない）が増えていないかも見る
- `human_verdicts` と rationale は Claude が下書きし、R-koma が確認して採用した（2026-10-08。rationale の先頭の【下書きは Claude、確認は R-koma】）

### 受け止めの方針を変え、測る基準を足す（#503、2026-10-09）

地図の経路の 49 件（中心は #480 以後の `2026-10-07-f04cfbc9`・`2026-10-08-7f7c60c6`）を読み、受け止めを厚くした手書きの応答を
既存の基準で採点した（調査の結果は #503 のコメント）。冷たく機械的に感じる原因の多くは、受け止めを 1 文に絞った方針ではなく、
直前の問いへの答えを無視する・「〜という見立てですね」と同じ文の形を続ける・正しい部分に触れずに訂正する、の 3 つだった。

**決定（R-koma）**: 受け止めは、説明のどこが良いかを中身に触れて具体的に 1 文で示すのを基本とし、2 文目に「なぜそこが良いか」
「以前の発言・学習とのつながり」を許す。言い直し・補強・過剰な称賛・定型の励ましは今までどおり禁じる。誤りの訂正の前に、
本当に正しい部分を具体的に 1 句だけ受け止めるのも許す（説明全体を褒める前置きは禁じる）。旧経路のプロンプトは変えていない。

| 基準 | 変更 | instance |
| --- | --- | --- |
| `r1`（rubric） | 価値づけ・以前の発言や学習とのつながりを示す文は、説明し直していなければ補強にあたらないと明記した。手書きの 2 文の受け止め（「前回わからないままだった『いつ増やすか』に、自分なりの答えを出せています」）を confirm でも補強と判定し、`unlinked_prior_learning` が求める受け止めと逆を向いていたため | 全件（文面を変えたので全件の scoring で確かめる） |
| `r4`（rubric、新設） | `contains_stock_praise`（deterministic）。「完璧」「素晴らしい」「正解です」「大丈夫ですよ」などの語句。手書きの「素晴らしい考えですね！完璧です」は、どの基準でも fail にならなかった | 全 instance に `r4` のラベルを足した。該当する 5 件はすでに fail のレコード |
| `uncorrected_misconception` の `a3`（新設） | 誤りの指摘の前に（または代わりに）説明全体を肯定・称賛する前置き。正しい部分を具体的に挙げる受け止めと、使った言葉を挙げるだけのものは該当しない | fail: `2026-09-17-0f43b9c0__t8`・`2026-09-21-c7718f93__t8`・`2026-10-01-04d22b75__t8`、pass: `2026-10-01-25adb2ba__t8`・`2026-09-17-0f43b9c0__t8-exemplar` ほか |
| `ignored_learner_answer`（新設） | 学習者の発言が直前の問いへの答えを含むのに、答えに触れず、質問やついでの話だけを拾って（または何も受け止めずに）進む | fail: `2026-10-07-f04cfbc9__t16`・`2026-10-08-7f7c60c6__t8`・`2026-10-07-f04cfbc9__t18`、pass: `2026-10-07-f04cfbc9__t10`・`2026-10-08-7f7c60c6__t20`・`2026-10-07-f04cfbc9__t16-exemplar`（手書き） |

- 付け直したラベル: `2026-10-01-04d22b75__t8` は rationale に「冒頭が肯定的で誤りだと伝わりにくい」を基準外の弱点として書いて pass にしていた。
  `a3` で fail にした。`2026-10-07-f04cfbc9__t16` と `2026-10-08-7f7c60c6__t8` は annotate で pass だったが、`ignored_learner_answer` で fail にした
- `r4` は旧経路の「わからない」のモード（第一声を「大丈夫ですよ」にする指示）の応答を fail にする。旧経路の regression の値は、この基準を足す前と比べない
- 「温かさ」そのものは二値で書けない（判定者で割れる）ので測らない。答えの受け止め・具体的な受け止め・定型の称賛・前置きに分けて測る
- 同じ文の形の繰り返し（「〜という見立てですね」が続く）は、`repeats_previous_opening` が句の完全一致しか見ないので検出しない。
  プロンプトで禁じただけで、測る基準は作っていない（文末の形の一覧に依存する check は脆いため）
- `2026-10-01-25adb2ba__t8` の `r3` は、受け止めだけを書き換えた版で fail・元の応答で pass と割れた。受け止めとは関係のない `r3` の揺れの疑いがあり、
  #502 の校正で見る
- `ignored_learner_answer` の `a1` は、screen（Haiku）が「判定対象の応答の中の問い」や「学習者が疑問文で述べた案」を答えの側と
  取り違えた（FN）ため、手順と除外を criterion に書いた。書き直した後の 6 件は最終判定がすべて一致し、screen には pass の 2 件
  （`f04cfbc9__t10`・`f04cfbc9__t16-exemplar`）を fail とする誤り（confirm が覆す側）だけが残る
- judge を `claude-sonnet-5`（カスケードなし）にすると、`f04cfbc9__t16-exemplar` の `r1` を fail（1 文の受け止めを言い直しと判定）、
  `f04cfbc9__t18` の `r3` を pass と判定した。既定の judge では一致しており、judge のモデルを変えるときに見直す
- `human_verdicts` と rationale は Claude が下書きし、R-koma が確認して採用した（2026-10-09。rationale の先頭の【下書きは Claude、確認は R-koma】）

---

## フィードバックの理解度（#483、2026-10-08）

学習・復習の終わりにフィードバックが付ける `understanding_level`（high / medium / low）を、人間のラベルとの一致で測る。
応答の golden・judge の仕組みとは別に持つ（`evals/feedback.py`・`datasets/feedback.jsonl`。`eval.py` には足さない）。

- 正本は `datasets/feedback.jsonl`（1 行 = 1 セッションのフィードバック）。`evals/tools/capture_feedback.py` が、本番の
  `analyze_dialogue` → `score_feedback`（`graph/nodes/_feedback_assessment.py`）に渡した入力（会話・ノート・観点マップ）と、
  `feedbacks` の行を写す。地図の経路の学習では、評価には渡していない `depth_map` / `map_covered` も参考に持つ
- ノートの本文は capture の時点の `notes.content` なので、後の復習で書き換わった・後で手で編集されたノートのフィードバックは
  capture しない。**セッションの直後に capture する**
- ラベルは全体の 3 段階（`human_level`）と `note` だけ。甘い・厳しいの方向は人間と LLM の段階の差から決める（2026-10-08 決定）。
  annotate の UI（`/feedback`）は、人間が付け終わるまで LLM の判定を見せない（引きずられないため）。基準は本番のプロンプトの
  3 段階の説明をそのまま見せる
- 判断に使う件数の目安は 30 件・人間が low とする例 8 件以上（2026-10-08 決定）。浅い説明で終えるセッションを意図して混ぜる
- 採点は完全一致で決定的に行い、judge は使わない。主に見る値は、一致率・混同行列・**人間が low なのに LLM が medium 以上の割合**
  （`low_overrated`。#460 で間隔を伸ばす誤りに当たる）・同じ入力を `--runs` 回評価したときに判定がそろう割合
- regression は run ごとに 1 件として一致を数える。揺れの集計はラベルの無いレコードも含む


---

## 確認待ちの項目（`pending/`、#563、2026-10-13）

プロンプト・golden・judge の基準を変えた PR のうち、eval でまだ確かめていない項目を `pending/<issue>.yaml` に持ち、
`python -m evals.verify <report>` でレポートと照合する（API は呼ばない）。全件の regression 1 回で、複数の変更の確認をまとめて済ませるため。

### 運用

- **プロンプト・golden・judge の基準を変える PR は、同じ差分で `pending/<issue>.yaml` に項目を足す**（無ければ作る。PR ではなく Issue ごと）
- 確認は 2 段に分ける
  - **issue ごと**: その issue の instance だけを `--trace` と `--no-cascade` で回す。後の作業がその修正を前提にする変更（事前分析など上流の決定を変える・ベースラインの前提になる）と、同じプロンプトの同じ箇所を複数の issue が直す変更だけ
  - **まとめて**: 全件の regression（golden か基準を変えた項目があれば scoring も）を回し、`evals.verify` で全項目を照合する。外れた instance は、項目の一覧で効きうる変更を絞り、`--trace` で変更前のコミットと比べる
- `evals.verify` は各項目に `status`・`checked_on`・`report`・`result` を書き戻す。`人が読む` の項目は、出力された応答を読んだ人が `status` に `合格` / `不合格` を書く
- ファイルの全項目が `合格` / `不合格` になったら、コマンドが出す Markdown の要約を Issue にコメントし、ファイルを消す（記録は Issue と git の履歴に残る）。`不合格` の項目は、該当する Issue に結果を書いて直す
- 一覧は `python -m evals.verify --list`。項目の形は `tests/unit/evals/test_verify.py` が検査する

### 項目の形

```yaml
issue: 536
prs: [559]
summary: 何を変えたか
items:
- id: map-r1                 # ファイルの中で一意
  run:                       # 照合に使えるレポートの実行条件。合わなければ「対象外」
    mode: regression         # regression / scoring
    replay_mode: full        # regression だけ。full / pinned
    route: map               # map / legacy / all
    runs: 3                  # regression だけ
    cascade: true            # カスケードで採点したレポートか（false は --no-cascade）
  target:                    # 省くとレポートの全件。failure_mode を省いた traces は、その trace を持つ全 failure_mode の instance が対象（全件の値を今の instance に固定するとき）
    failure_mode: ignored_learner_answer
    traces: [2026-10-07-f04cfbc9__t16]   # または exclude_traces
  value: r1                  # assertion id / verdict / turn_analysis.<key>（equals も書く）/ calibration.final（scoring）
  expect:                    # 数で判定する条件
    passes: 83               # all / 整数（of と組）/ baseline: <evals/ からのレポートのパス>
    of: 90
    tolerance: 2             # 省くと passes: all は 0、ほかは 2
  status: 未確認             # 未確認 / 合格 / 不合格 / 人が読む / 対象外
```

本文を読む条件は `expect` の代わりに `read: <読む条件>` を書いた別の項目にする（`人が読む` になり、対象の応答を並べて出す）。
regression は pass の回数、scoring は judge と人のラベルが一致した回数を数える（適用外の回は数えない）。

### 決定（R-koma、2026-10-13）

- **項目のファイル**: Issue ごとに 1 ファイル。1 つの Issue が複数の PR にまたがり、結果のコメント先も Issue のため。生成物の一覧（Markdown の表）は作らず、一覧はコマンドで出す
- **結果を残す場所**: 照合のコマンドが項目に書き戻す。全項目が済んだら Issue にコメントしてファイルを消す
- **「悪化しない」の許容幅**: 比べる相手から 2 件減るまでは合格、3 件以上減ったら不合格（件数で判定）。項目ごとに `tolerance` で上書きでき、「3/3 pass」のような条件は 0。
  根拠は、#503 の確認で変えていない部分でもカスケードの `r1` が 84→83/90・`r3` が 87→88/90 と 1 件ずつ動いたこと。不合格のときは、新しく fail になった instance の応答と judge の理由を並べて出す
- **カスケードでの採点し直し**: eval 本体の `--rescore-report <report>` に置く（保存済みの regression の応答を、今の judge の設定で採点し直す。judge のキャッシュに乗る。runs・replay・route・trace とプロンプトの値は元のレポートを引き継ぎ、`meta.rescored_from` に元の名前を残す）。
  照合のコマンドは API を呼ばず、レポートの実行条件（`route`・プロンプトの fingerprint・runs・カスケードの有無・instance）が項目と合わなければ `対象外` とし、理由とそろえるためのコマンドを出す。比べるレポートが screen だけの採点なら、それを採点し直すコマンドを出す
- 照合に使うレポートの fingerprint は、照合する時点のコードの値（`MAP_PROMPT_FINGERPRINT` / `PROMPT_FINGERPRINT`）と一致する必要がある。後の PR がプロンプトを変えたら、前の項目もその後のプロンプトで回したレポートで確かめる
- `PENDING_VERIFICATION.md` から移したのは #536 の項目だけ。#503・#506 の項目は合格か、該当する Issue に戻した記録で、結果は #503・#506 のコメントにある。
  #536 の比べる相手（#503 の確認のレポート）は残っていないので、#503 に記録した数（`r1` 83/90・`r3` 88/90、`ignored_learner_answer` の t16・t18 は 5/6）を基準にし、記録の無い正例（t10・t20）は全 pass を求める

### 質問の質を測る基準の 1 回目（2026-10-16、#502）

正本 115 件（全件ラベル済み）で error analysis をした。質問に関わる失敗で最も多いのは「答えを渡してから問う」で、
同じ応答の中で答えを述べるもの（`r3`・`self_answered_question`）のほかに、問いの前に対比・定義を先に述べるもの
（`preempted_learner_explanation`）と、前のターンで自分が説明したことを問い直すもの（`reasked_own_explanation`）があった。後の 2 つは測っていなかった。

| 変更 | 内容 | instance |
| --- | --- | --- |
| `preempted_learner_explanation`（新設） | 学習者に考えさせる・説明させる内容（名前と定義・対比・理由・利点）を問いの前に AI が先に述べる。学習者がまだ口にしていない用語を、知っているかを問わずに名前と定義から入る場合も該当。質問・説明の依頼・「わからない」への説明と、受け止め・訂正は該当しない | fail: `2026-10-01-04d22b75__t6`・`2026-09-30-f5b46d76__t8`、pass: `2026-09-30-f5b46d76__t8-exemplar`（手書き）・`2026-09-30-7b546521__t8` |
| `assumed_unmentioned_concept` | instance を足した | fail: `2026-10-08-7f7c60c6__t12`・`__t22`・`2026-10-01-758bf1fd__t6` |
| `unclear_question` | instance を足した | fail: `2026-09-29-e9cb80a7__t10` |

- **用語の導入はユーザーの方針（2026-10-16）**：新しい用語を導入するときは、名前と定義を先に述べず、まず学習者が知っているかを問い、知っていれば説明させる。
  展開のモードの指示（`graph/prompts/question.py` の `_MODE_EXPAND_SECTION` の「前提となる新しい知識の補足は簡潔に」）はこれと食い違う。#502 の「直す」で見直す
- **「浅いが正しい問い」は測らない**：二択・具体例を挙げさせるだけの問いは、人のラベルが pass。「理由・仕組みを引き出す」を fail の基準にするとラベルと食い違うので、基準値の後に必要ならペア比較を検討する
- **問いの長さの deterministic な check は作らない**：問いの文の長さの中央値は pass 106 字・`unclear_question` 127 字・ほかの fail 134 字で、分かりにくさを分けない
- 2026-10-05 に `preempted_learner_explanation` をラベルだけの型にした決定（この節の上の「応答の反復・…」）は改めた。未出の概念を前提に問う問題は 2026-10-06 に `assumed_unmentioned_concept` へ分けてあり、この golden は先に述べる側だけを測る
- `reasked_own_explanation` は fail 1 件だけなので、golden は作らずラベルとしてだけ使う（2 節の規約）
- `2026-10-05-898f8ee5` は「この仕組み」のままトピックを訂正したセッション（#458・聞き取りの `topic_is_clear` より前）で、入力に誤った地図を含む。golden に昇格しない。地図が原因の t6・t26・t28・t30 は note に【地図起因】がある
- `human_verdicts` と rationale は Claude が下書きし、R-koma が確認して採用した（2026-10-16。rationale の先頭の【下書きは Claude、確認は R-koma】）
- **1 回目の scoring で直した基準**（2026-10-16。校正ゲートと `preempted_learner_explanation` は合格、足した instance のうち 2 件で judge が人とずれた）
  - `assumed_unmentioned_concept` の `a1`：`758bf1fd__t6`（エラーバジェットの残りが少ないとき信頼性と開発速度をどう両立するか）を judge は「日常のトレードオフの考え方で答えられる」と pass にした。
    基準が「専門的な概念・用語」だけを対象にしていて、方法を問い、答えるにはその分野の具体的なやり方を知っている必要がある問いを含んでいなかった。「手法」と、方法を問う場合を足した
  - `unclear_question` の `a1`：`e9cb80a7__t10`（ファイルを読む 3 つの手順を示し、そのどこで「写真を表示する処理」が始まるかを問う）を judge は「手順のどれかを答えればよいと一読で分かる」と pass にした。
    問題は文の分かりにくさではなく、問いの前提（示した手順）に問われているものが無いこと。前提の中では答えようがない問いを足した
- **2 回目の scoring で直した基準**（2026-10-16。`assumed_unmentioned_concept` の 3 件は合格。今 pass の instance は変わらなかった）
  - `unclear_question` の `a1`：screen の judge は `e9cb80a7__t10` を「前提の中では答えようがない問いになっている」と書きながら holds=false を返した。
    基準の 1 文目が「一度読んだだけでは何を答えればよいか分からない」のままで、足した場合を「も含む」で付け足していたので、文が読めるかだけで判断した。
    1 文目を「問いの書き方のせいで、何を答えればよいか分からないか、答えようがない」にし、該当する場合を（1）〜（3）の並列に組み直した。
    `assumed_unmentioned_concept` と重ならないよう、学習者がまだ知らない知識を要することだけでは該当しないとした
- **3 回目の scoring で直した基準**（2026-10-16）：組み直した後も、screen の judge は `e9cb80a7__t10` を「提示された前提の中では答えようがない」と書きながら holds=false を返した。
  judge には「記述が成り立つなら holds=true」と指示しているのに、基準が「問いとして成り立っていない」「答えようがない」と否定で書いてあり、否定の向きを取り違えたと見た。
  基準を「応答の問いに、次のどれかの欠陥がある」と肯定の形にし、（1）〜（3）からも否定の言い回しを外した（（3）は「問われているものが、前提にする選択肢・手順・場面の外にある」）
- **`e9cb80a7__t10` は screen の既知の見落としとして残す**（2026-10-16）：肯定の形にした 4 回目も、screen の judge は「判定基準の欠陥（3）に該当します」と書きながら holds=false を返した。
  文面を 3 通り変えても同じなので、基準ではなく screen（Haiku）がこの instance で理由と holds を食い違えると見て、基準はこれ以上直さない。
  カスケードは screen の fail だけを confirm に回すので、この見落としは最終判定に残る（`unclear_question` の `a1` は 5/6）。ラベルは fail のまま、instance も golden に残す。
  校正ゲート（final）は合格（TPR 95%・TNR 100%・正例 32/32、`20261016T125946Z-scoring.json`）。同じ型の見落としが regression でも出ると、`unclear_question` の（3）の問いは数え漏れる
- **基準値 `baselines/map-v5-full.json`**（2026-10-16。`map_prompt_fingerprint=46f81c2f62ba`・地図の 41 instance × 3 回・カスケード）：全 assertion が pass した回は 113/123。
  質問の質の golden は `preempted_learner_explanation` の `a1` 8/9、`assumed_unmentioned_concept` の `a1` 13/15、`unclear_question` の `a1` 10/12。rubric は `r1` 116/117・`r3` 119/123。
  同じ応答を `--no-cascade` で採点し直した記録は `map-v5-full-screen.json`。#569・#611 の `map-unchanged`（v4 と screen だけで比べる項目）は、#531 の受け止めの 1 文を screen が `r1` 違反と誤判定するので比べられず、
  #531 の後をカスケードで測った #536 の `map-r1`・`map-r3` で代えた（R-koma 確認）
- **プロンプトの修正**（2026-10-17。地図の経路だけ。`map_prompt_fingerprint` は `2ec014b2c769`）：基準値で fail した 10 回のうち、5 回は問いの答えを問いの前に述べ（`r3`・`preempted`）、2 回は学習者が触れていない概念を前提に問うた（`assumed`）。
  用語を先に定義してから問う形が両方に絡むので、まだ口にしていない用語は名前と定義を先に述べず、知っていれば説明してもらう問いにした（共通ルール・展開のモード・深掘りの未出の概念の規則。展開のモードに悪い応答と良い応答の例を足した）。
  「わからない」への支援と質問への回答では、求められた範囲の説明を続けて許す。あわせて、送信前に問いより前の文に答えの中核を書いていないか確かめる手順を共通ルールに足した。旧経路（`question.py`）は変えていない。
  確かめる項目は `pending/502.yaml`
- **触れていない観点の規則**（2026-10-17。`map_prompt_fingerprint` は `2047bbe3aa76`）：上の修正で fail した 6 instance を `--trace` で確かめた（`20261016T154421Z-regression.json`）。fail は 7 回から 5 回に減り、用語を先に定義する形は無くなった（ACID は 3 回とも「知っていたら説明してもらえますか」）。
  ただし `7f7c60c6__t12` は 2/3 から 3/3 fail に増えた。学習者がまだ触れていない観点（油彩）で、名前と定義は述べなくなったが、知っている前提で性質（油絵具でどう描けるか）を問うた。
  そこで、選んだ観点が `map_covered` に無いときだけ、その観点の性質・働き・理由を問わず、言葉を知っていれば説明してもらう規則を核心の節に足した
- **`assumed_unmentioned_concept` の基準に、用語を知っているかを問う形の除外を足した**（2026-10-17、R-koma の決定）：上の規則で `7f7c60c6__t12` を `--trace` で確かめると（`20261016T163759Z-regression.json`）、
  「油絵具という言葉を知っていたら、どんな絵具か説明してもらえますか？」という方針どおりの問いを、judge が「未説明の用語の知識が要る」と fail にした。
  `preempted_learner_explanation` の手書きの正例（ACID を知っているかを問う）と同じ形の問いに、2 つの基準が逆の判定を出していた。
  `a1` に「まだ述べていない用語について、その言葉を知っているかを確かめ、知っていれば説明してもらう問いも該当しない」を足し、同じ入力への手書きの正例 `7f7c60c6__t12-exemplar` を足した
- **除外を絞った**（2026-10-17）：除外を足した後の scoring（`20261016T165034Z-scoring.json`）で、正例は pass になったが、元の fail の `7f7c60c6__t12`（油絵具の乾く速さや色の重ね方の特徴を問う）を confirm の judge が「観点を示して推測を促しているので答えられる」と pass にした（前回の scoring では fail）。
  除外に添えた「（知らなければそう答えられる）」が、推測で答えられる問いまで許す方向に読まれたと見て、除外を「言葉を知っているかと、それが何かだけを尋ねる問い」に絞り、性質・働き・使い道を問う場合は当たらないと明記した

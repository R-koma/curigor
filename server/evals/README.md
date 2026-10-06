# evals — `generate_question` の振る舞い評価

`learning_dialogue`（`prepare_turn` → `respond`）が出す質問の振る舞いを、人間の判断基準（golden）に照らして LLM judge が採点し、その judge 自体が信頼できるかを人間ラベルとの一致で測る。

- 実行コマンドは `CLAUDE.md` の「開発コマンド」節。
- 対象は `generate_question` のみ。review_dialogue・note・feedback は対象外
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
confirm（既定 Opus 5）に回す。** `--judge-model` が screen、`--confirm-judge-model` が confirm、
`--no-cascade` で従来の単一 judge に戻せる。

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

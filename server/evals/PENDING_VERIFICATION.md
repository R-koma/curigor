# eval の確認待ち

プロンプト・golden・judge の基準を変えた PR のうち、eval でまだ確かめていない項目の一覧。
まとめて全件を回すとき（地図のベースラインを取るときなど）に、この一覧で照合する。

## 運用

- **プロンプト・golden・judge の基準を変える PR は、同じ差分でここに項目を足す**
- 確認は 2 段に分ける
  - **issue ごと**: その issue の instance だけを `--trace` と `--no-cascade` で回す。後の作業がその修正を前提にする変更（事前分析など上流の決定を変える・ベースラインの前提になる）と、同じプロンプトの同じ箇所を複数の issue が直す変更だけ
  - **まとめて**: 全件の regression（golden か基準を変えた項目があれば scoring も）を回し、前の修正を壊していないかを見る。外れた instance は、この一覧で効きうる変更を絞り、`--trace` で変更前のコミットと比べる
- 項目は「未確認」の行が無くなったら、結果を issue にコメントしてから消す（記録は issue と git の履歴に残る）。外れた項目は、該当する issue に結果を書いて直す

## 項目の書き方

```markdown
### #<issue>（PR #<pr>）<何を変えたか>

- 変えたもの: <ファイル・golden・基準>
- 必要な実行: <scoring --strict / regression full / regression pinned>

| 状態 | 実行 | instance | 見る値 | 合格の条件 |
| --- | --- | --- | --- | --- |
| 未確認 | regression full | `<trace_id>` | `turn_analysis.<key>` | <条件> |
```

状態は `未確認` / `合格（日付・レポート）` / `不合格（日付・どの issue に戻したか）`。

#507・#506 の scoring は、PR のマージ前に回したレポートから転記した。golden の本文がマージ時と違えば、まとめての scoring で判定し直される（変わっていなければ判定キャッシュが効く）。

---

### #507（PR #512）地図の事前分析の `has_misconception` の基準

- 変えたもの: `graph/prompts/map_turn_analysis.py` の誤りの基準、golden `premise_shifting_correction.yaml`（新規）
- 必要な実行: regression full（t22 のカスケードでの確認だけ残る。まとめて）

| 状態 | 実行 | instance | 見る値 | 合格の条件 |
| --- | --- | --- | --- | --- |
| 合格（2026-10-08・`20261008T072928Z-regression.json`） | regression full | `2026-10-08-7f7c60c6__t16` | `has_misconception`・本文 | 3 回とも false、否定しない |
| 合格（同上） | regression full | `2026-10-07-f04cfbc9__t24` | `has_misconception`・本文 | 3 回とも false、否定しない |
| 合格（同上） | regression full | `2026-10-01-04d22b75__t8` | `has_misconception`・本文 | 3 回とも true、誤りを訂正する |
| 合格（同上） | regression full | `2026-10-01-25adb2ba__t8` | `has_misconception`・本文 | 3 回とも true、誤りを訂正する |
| 未確認 | regression full（カスケードあり） | `2026-10-07-f04cfbc9__t22` | rubric `r1` | pass。`--no-cascade` では screen が 3 回とも fail（言い直しと判定）。`has_misconception` は 3 回とも false で a1 も pass なので、#507 とは別。confirm でも fail なら、#510・#511 より前のコミットと比べる |
| 合格（2026-10-07・`20261007T175316Z-scoring.json`） | scoring | `premise_shifting_correction` の 3 件 | judge と `human_verdicts` の一致 | 一致する。9 判定すべて一致（元の t22 の応答の `r1` は screen で pass） |

### #506（PR #511）以前の学習に触れたらつなげる

- 変えたもの: `graph/prompts/map_question.py`・深さの地図のプロンプト、golden `unlinked_prior_learning.yaml`（新規）
- 必要な実行: regression full（まとめて）。scoring は `a1` の見逃しの扱いを決めてから

| 状態 | 実行 | instance | 見る値 | 合格の条件 |
| --- | --- | --- | --- | --- |
| 未確認 | regression full | `2026-10-07-f04cfbc9__t12` | verdict | pass（応答がつながりを示す） |
| 未確認 | regression full（カスケードあり） | `2026-10-07-f04cfbc9__t24` | verdict | pass。`--no-cascade` では 3 回とも pass（2026-10-08・`20261008T072928Z-regression.json`）。ただし judge は元の応答の `a1` を見逃したので、pass だけでは信用できない。本文がつながりを示しているかを読む |
| 不合格（2026-10-07・`20261007T175038Z-scoring.json`） | scoring | `unlinked_prior_learning` の 3 件 | judge と `human_verdicts` の一致 | 一致する。`2026-10-07-f04cfbc9__t24` の `a1` で judge が pass・人が fail（見逃し）。ほかの 8 判定は一致。基準の文面を見直すかを判断する |

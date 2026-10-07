# まとめノートの候補（埋め込みの類似度）: 現状と改善の余地

## 現状

まとめノートに入っていないノートに、近いノートが入っているまとめノートを、束ね先の候補として出す（#396）。
候補は `notes.suggested_collection` に入り、画面のバナーで採否を選ぶ。自動では束ねない。

- 実装: `server/services/collection_suggestion.py`、`server/repositories/note_embedding_repository.py` の `find_collection_votes`
- 呼ぶ場所: 埋め込みを作り直した直後（`refresh_note_embedding`）と、`scripts/backfill_note_embeddings.py` の 2 周目
- 候補を入れない条件: 束ね済み・候補あり・断られた（`collection_suggestion_dismissed_at`）・まとめノートから外された

## 暫定の値

| 設定（`server/core/config.py`） | 既定 | 意味 |
| --- | --- | --- |
| `COLLECTION_SUGGESTION_MIN_SIMILARITY` | 0.5 | 近いノートとして数える、コサイン類似度の下限 |
| `COLLECTION_SUGGESTION_NEIGHBORS` | 10 | 比べる近いノートの件数 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 埋め込みのモデル |
| `MAX_EMBEDDING_INPUT_CHARS` | 6000 | 埋め込みに渡す文字数の上限 |

集計は、まとめノートごとに近いノートの類似度を合計し、最も大きいまとめノートを選ぶ。

**0.5 は実データで決めた値ではない。** 日本語のノートで、同じ話題と無関係な話題の類似度がどこで分かれるかを、まだ測っていない。
この値は暫定で、設定を変えれば調整できる。改善の余地がある前提で使うこと。

## 調整の目安

| 症状 | 調整の向き |
| --- | --- |
| 候補がほとんど出ない | `MIN_SIMILARITY` を下げる。`NEIGHBORS` を増やす |
| 無関係なまとめノートが候補に出る | `MIN_SIMILARITY` を上げる |
| 小さいまとめノートより、大きいまとめノートが選ばれやすい | 集計を合計から最大値や平均に変える（下記） |

値を変えても、すでに入った候補は変わらない。入り直させたいときは、`suggested_collection` を NULL に戻して backfill を実行する。

## 測り方

`scripts.backfill_note_embeddings` を実行して埋め込みを作ったあと、次の問い合わせで、まとめノートの無いノートごとの近いノートと類似度を見る。

```sql
SELECT n.topic AS ノート, m.topic AS 近いノート, c.name AS まとめノート,
       round((1 - (a.embedding <=> b.embedding))::numeric, 3) AS 類似度
FROM note_embeddings a
JOIN note_embeddings b ON b.user_id = a.user_id AND b.note_id <> a.note_id
JOIN notes n ON n.id = a.note_id
JOIN notes m ON m.id = b.note_id
LEFT JOIN note_collections c ON c.id = m.collection_id
WHERE n.collection_id IS NULL
ORDER BY n.topic, 類似度 DESC;
```

人が見て「同じ話題」と判断できるノートの組と、無関係な組で、類似度がどこで分かれるかを確認する。
分かれ目より少し低い値を、`MIN_SIMILARITY` の候補にする。

## 改善の余地

- **しきい値を実データで決める。** 上の測定で、0.5 が高すぎるか低すぎるかを確かめる。モデルを変えたときも測り直す
- **1 位と 2 位の差を条件に入れる。** 2 つのまとめノートの点が近いときは、候補を出さないか、2 つ出す
- **集計を見直す。** 合計は、ノートの多いまとめノートが有利になる。最大の類似度や、まとめノートの平均で比べる案がある
- **断られた候補を使う。** いまは断った時刻だけを持ち、どのまとめノートを断ったかは残していない。残せば、同じ候補を出さない、しきい値を上げる、の根拠になる
- **LLM で最終確認する。** 類似度で候補を絞ったあと、ノートの要約とまとめノートの名前を見せて、束ねてよいかを聞く案。費用と遅延が増える
- **ユーザーごとに相対化する。** ノートの書き方やトピックの幅で、類似度の分布が変わる。ユーザーの全ノートの分布に対する順位で決める案
- **埋め込みの入力を見直す。** いまはトピック・要約・本文・復習の追記を連結している。要約だけにすると、短い話題どうしが近づく可能性がある

## 関連

- 別のまとめノートのノートとのつながりの候補（#396 の残り）も、この類似度を使う。目的が違うので、同じしきい値が適切とは限らない。別の設定にすることを検討する
- 学習中に過去のノートを引き合いに出す機能は、トピックと学習目的の短い文とノートを比べるので、ノートどうしより類似度が低く出やすい。別の設定 `RELATED_NOTES_MIN_SIMILARITY`（暫定 0.4）を持つ。取れたノートと類似度はサーバーのログ（`related notes:`）に出るので、それを見て調整する

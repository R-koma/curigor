# ADR-016: アカウントの削除は本人が行い、関連データを外部のものまで消す。データはアカウントがある間だけ保持する

## Status

Accepted（2026-10-15。実装は #598）。ADR-012 の項目 5 を具体化する

## Context

ADR-012 で、アカウントとデータの削除（項目 5）を別に入れることにしていた。それまで消せたのはノートとまとめノートだけで、削除の請求は問い合わせ窓口で受けて手で消す運用だった。

#595 で外部キーに `ON DELETE CASCADE` / `SET NULL` を付け、`user` を消せば DB の行は消えるようになった。それでも次は残る。

- LangGraph のチェックポイント（`checkpoints` 系のテーブル。`thread_id` = セッション ID で、`user` と外部キーでつながっていない）
- ストレージ上の対話の添付画像（`dialogue_message_images.storage_key`）
- アバターのファイル（`client/public/avatars/`）
- Langfuse の trace（発言・応答・ユーザー ID・セッション ID）

ほかに、保持期間の定めが無く、`account` テーブルには、アプリが使っていない Google の access / refresh / ID token が保存されていた。

## Decision

1. **経路**: BetterAuth の `deleteUser` を有効にする。`beforeDelete`（`client/lib/auth.ts`）が `auth.api.signJWT` で `purpose: "account-deletion"` を持つ JWT を作り、FastAPI の `DELETE /api/account/data` を呼ぶ。この API は `purpose` の無い通常の API 用の JWT を 403 で断る。FastAPI はチェックポイントと、セッションごとの添付画像の置き場所（`dialogue_images/{session_id}/`）全体と、Langfuse の trace を消す。画像を置き場所ごと消すのは、メッセージの取り消し・巻き戻しで行だけが消えたファイルも残さないため。続けて Next がアバターを消し、BetterAuth が `user` を消す。DB の行は CASCADE で消える。API が失敗したら例外で止め、`user` は消さない。手順はどれも何度実行しても成功するので、もう一度押せば最後まで進む
2. **本人の確認**: 確認ダイアログに加え、ログインから `freshAge`（BetterAuth の既定の 1 日）以内のセッションであることを求める。過ぎていれば `SESSION_EXPIRED` で断り、ログインし直してもらう。メールでの確認は使わない
3. **Langfuse**: API で `userId` の trace を一覧して消す。失敗してもアカウントの削除は止めず、warning のログに残す。消し損ねた分は Langfuse の保持期間に任せる
4. **保持期間**: 対話の全文・放棄したセッション・ノートなどは、アカウントがある間は保持し、削除で消す。BetterAuth の `session`（IP・UA）は失効するまで。期限を過ぎたデータを消す定期処理は作らない
5. **Google の token**: 保存しない。`client/lib/auth-hooks.ts` の account の hook で null にし、既存の行はマイグレーションで null にした。ログインに要るのは `accountId` だけ
6. **取り消し期間**: 設けない。削除は即時の物理削除で、論理削除の列は作らない

## Reasons

- **BetterAuth の `deleteUser` を使う理由**: 本人の確認とセッション・cookie の後始末を BetterAuth に任せられる。外部のデータを消すのは本人の確認が通った後だけになる。FastAPI だけで消す案は、JWT からセッションがいつ作られたかが分からず、本人の確認を足せない
- **メールで確認しない理由**: Resend のドメインが未認証で、開発者以外にはメールが届かない。Google でログインしたユーザーにはパスワードも無い
- **Langfuse の失敗で止めない理由**: 外部サービスの障害で、本人が自分のデータを消せなくなるのを避ける。trace は運用の観測用で、本体のデータではない
- **定期削除を作らない理由**: 利用者はまだ少ない。放棄したセッションも再開と履歴の表示に使うので、期限で消すとその挙動と衝突する
- **取り消し期間を設けない理由**: 論理削除にすると、全クエリでの除外と期限後の削除処理が要る。確認ダイアログと本人の確認で誤操作は十分に防げる

## Consequences

- `user` を参照するテーブルを足すときは `ON DELETE CASCADE` を付ける。`user` とつながらない保存先（別のストレージ・外部サービス）を足すときは、`server/services/account_deletion.py` に消す処理を足す
- 削除の最中に別のタブで応答の生成が進んでいると、削除の後に書かれたチェックポイント・画像が残りうる。`user` とつながらないので、サーバーの起動時の裏で、`dialogue_sessions` に無い `thread_id` のチェックポイントと `dialogue_images/` の直下の置き場所を消す（#661、`server/services/orphaned_session_data.py`）。削除の直前に送られた Langfuse の trace も、取り込みが終わる前で一覧に出ず残りうる（保持期間に任せる）
- `user` の削除だけが失敗すると、DB の行は残り、画像は無い状態がありうる。もう一度削除すれば解消する
- ノート・まとめノートを 1 つずつ消すときは、チェックポイントと添付画像が残る（#659）
- S3 の実装（#128）でも、`ObjectStorage.delete` と `delete_prefix` は、無いキー・空の置き場所を渡されても成功させる。`list_child_prefixes` は区切り `/` の CommonPrefixes から名前を返す
- プライバシーポリシー（ADR-012 の項目 3）に、この保持期間と削除の手順を載せる（#662）
- 保持期間は、第三者の利用者が増えたとき、放棄したセッションが容量を圧迫したとき、組織単位で導入するとき（#599）に見直す
- Google の API を使うことになったら、token を保存しない hook とこの決定を見直す

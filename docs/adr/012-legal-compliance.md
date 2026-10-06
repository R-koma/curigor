# ADR-012: 第三者へ公開する前に、AI の表示・利用規約・プライバシーポリシー・同意の記録をそろえる

## Status

Proposed（2026-10-06）。実装は保留。第三者に使ってもらう前（招待制のベータを含む）に実装する

本書は調査に基づく方針で、法的助言ではない。公開前に、規約とプライバシーポリシーの本文を専門家に確認してもらう

## Context

いまは開発者本人だけが使っており、AI であることの表示・利用規約・プライバシーポリシー・同意の取得がどれも無い。第三者に公開すると、次の義務と要求がかかる。

- **個人情報保護法**: 利用目的の公表・通知（21 条）、保有個人データに関する事項（運営者の氏名・住所、開示などの請求の手続き）を本人が知り得る状態にすること（32 条）。外国にある第三者へ個人データを提供するには、本人の同意か、基準に適合する体制の整備と情報提供が要る（28 条）
- **消費者契約法 8 条**: 事業者の損害賠償責任を全部免除する条項と、故意・重過失による責任を一部でも免除する条項は無効になる。「一切責任を負わない」と書いても効かない
- **EU AI 規則 50 条**（2026-08-02 から適用）: EU の利用者がいるなら、AI と対話していることをその場で知らせる義務がある
- **OpenAI の規約・ドキュメント**（2026-10-06 に原文を確認）
  - TTS: 「Our usage policies require you to provide a clear disclosure to end users that the TTS voice they are hearing is AI-generated and not a human voice.」（Text to speech ガイド）
  - 未成年: API の契約（OpenAI Services Agreement v.010126 の 3.3 (c)）は、顧客が利用者に「allow minors to use OpenAI Services without consent from their parent or guardian」させることを禁じる。「13 歳以上」の条件は ChatGPT 向けの Terms of Use のもので、API の契約には無い
  - 13 歳未満: Under-18 guidance は「You should not use OpenAI services to process any personal data of children under 13 or the applicable age of digital consent without first implementing zero data retention in our API.」とし、未成年に出す応答を年齢に合ったものにする措置（フィルター・監視・必要なら年齢確認）も求める
  - 同意: Services Agreement 3.2 は、OpenAI がサービスを提供するのに必要な同意を顧客が利用者から得ることを求める
- **AI 事業者ガイドライン**（総務省・経産省）: 法的拘束力は無いが、AI の限界と誤りの可能性を利用者に説明することを求める
- **電気通信事業法の外部送信規律**: Curigor のサービスの区分が対象に当たるかははっきりしない。プライバシーポリシーに 1 節足せば安く対応できる

### 利用者のデータの送り先（2026-10-06 時点のコード）

| 送り先 | 所在 | 送るもの | 箇所 |
|---|---|---|---|
| OpenAI（対話） | 米国 | 発言・会話履歴・添付画像・ノート / フィードバック生成の入力 | `server/graph/llm.py` の `llm` / `llm_structured` |
| OpenAI（文字起こし） | 米国 | 録音した音声 | `server/transcription/` |
| OpenAI（読み上げ） | 米国 | 応答の本文 | `server/speech/` |
| Langfuse Cloud | `LANGFUSE_BASE_URL` のリージョン | 発言・応答・ユーザー ID・セッション ID | `server/observability/langfuse_tracing.py` |
| Google | 米国 | ログイン時に Google から氏名・メール・アイコンを受け取る | `client/lib/auth.ts` の `socialProviders.google` |
| Anthropic | 米国 | eval の採点で、capture したレコード（実セッションの会話）を送る | `server/evals/eval.py`（`llm_judge`） |
| 自前のストレージ | 自前 | 添付画像・アバター | `server/storage/`・`client/app/api/upload-avatar/` |

Anthropic へ送るのは開発者が eval を実行したときだけだが、第三者の会話を capture すると送り先に入る。

## Decision

**第三者に公開する前に、次の 1〜4 を 1 つの PR で入れる。アカウントの削除（5）は別の PR にする。**

1. **AI であることの表示**: チャットの入力欄の下に「Curigor は AI です。誤りを含むことがあるので、重要な内容は確かめてください」を常に出す。読み上げる場所のすべてに「AI の音声です」を出す。`VoicePanel` のほか、声で話していないときの ▶（`MessageSpeechButton`）も読み上げるので、そのラベルにも入れる
2. **`/terms`（利用規約）**: 免責は「故意・重過失を除き、責任の上限は〇〇」の形にする。ほかに、禁止事項、ノートの権利は利用者にあること、アカウントの停止、規約の改定、準拠法（日本法）と管轄。利用は **18 歳以上** に限る（理由は Reasons）
3. **`/privacy`（プライバシーポリシー）**: 取得する情報、利用目的、上の表の送り先（国名・その国の個人情報保護の制度の情報・送り先の講じる措置）、外部送信、保存期間、開示・訂正・削除などの請求の窓口、安全管理措置
4. **同意の記録と、未同意の利用者を止める仕組み**
   - サーバーに同意の記録（`user_id`・規約の版・同意した日時）を保存する
   - アプリ（`(main)`）に入る前に、現在の版に同意していなければ同意画面を出し、同意するまで先へ進ませない
   - 同意画面には、規約とプライバシーポリシーへのリンク、外国にある第三者への提供への同意を含める
   - 規約の版を上げると、全員に再同意を求める
5. **アカウントとデータの削除**（別 PR）: いまはノートとまとめノートの削除しかない。BetterAuth のユーザー、対話、ノート、ストレージの画像、チェックポイントを消す経路を作る。Langfuse の trace の扱い（保持期間に任せるか、消すか）もここで決める

### 運営者の表記

- ページには運営者の氏名（個人）と問い合わせ用のメールアドレスを載せる。住所は「請求があれば遅滞なく回答する」と書いて載せない（32 条は、求めに応じて遅滞なく回答する形を認めている）
- **氏名とメールアドレスは未定**。実装時に 1 か所の定数にまとめ、決まるまでは公開しない

### 今はやらないこと

- 特定商取引法に基づく表記: 有料プランを出すときに入れる
- 年齢確認（生年月日の入力など）: 規約で 18 歳以上と定め、同意画面で表明させるだけにする

## Reasons

- **同意を記録して止める方式にした理由**: Google ログインはサインイン画面からも新規アカウントを作れるので、サインアップ画面のチェックボックスだけでは同意を経ずに登録できる。記録を残せば、外国にある第三者への提供（28 条）への同意の証拠になり、規約を改定したときに再同意も取れる。既存の利用者にも同じ仕組みで同意を求められる
- **AI の表示を入力欄の下に常に出す理由**: EU AI 規則は、利用者が実際に目にする場所で知らせることを求める。規約の中だけに書いても足りない。誤りの可能性を画面で知らせておくと、規約の免責の根拠にもなる
- **18 歳以上に限る理由**: 未成年を受け入れると、保護者の同意の取得（Services Agreement 3.3 (c)）、13 歳未満のデータを送る前の zero data retention の申請、年齢に合った応答にする措置が要る。学習アプリには学生が来るが、今の規模でこれらを整えるより、規約で 18 歳以上に限るほうが安い。未成年を受け入れるときは、この 3 つをそろえてから規約を改定する
- **免責を全部免除にしない理由**: 消費者契約法 8 条で無効になり、条項全体の効力が争われる

## Consequences

- 実装するときに決めること: 同意の記録をサーバー（Alembic のテーブル + REST）に置くか、BetterAuth の `user` の追加フィールドに置くか。後者は `client/better-auth_migrations/` の再生成が要る。同意を確かめる場所（`(main)/layout.tsx` のサーバー側か、`MainLayoutClient` か）
- 送り先を増やしたら（S3 の本番化 #128、別の LLM や分析ツールの追加）、上の表とプライバシーポリシーを直し、必要なら規約の版を上げて再同意を取る
- 実際に第三者の会話を eval に capture するなら、プライバシーポリシーの利用目的に「品質の改善」と Anthropic への提供を含めておく
- 削除（5）が入るまでは、削除の請求は問い合わせ窓口で受けて手で消す

## References

- [OpenAI Text to speech ガイド](https://developers.openai.com/api/docs/guides/text-to-speech)
- [OpenAI Services Agreement（v.010126, PDF）](https://cdn.openai.com/osa/openai-services-agreement.pdf)
- [OpenAI Under-18 guidance](https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance)

- [EU AI Act Article 50 transparency obligations (2026)](https://secureprivacy.ai/blog/eu-ai-act-article-50-transparency-obligations-for-chatbots-and-deepfakes-2026)
- [個人情報保護法ガイドライン（外国にある第三者への提供編）](https://data.e-gov.go.jp/data/en/dataset/ppc_20170209_0002/resource/d3be57e6-0994-49df-925b-05b962e461ee)
- [総務省 外部送信規律](https://www.soumu.go.jp/main_content/001049133.pdf)
- [消費者契約法 第 8 条](https://ja.wikibooks.org/wiki/%E6%B6%88%E8%B2%BB%E8%80%85%E5%A5%91%E7%B4%84%E6%B3%95%E7%AC%AC8%E6%9D%A1)
- [AI 事業者ガイドライン](https://www.city.osaka.lg.jp/ictsenryakushitsu/cmsfiles/contents/0000623/623850/JigyousyaGuideline_1.0.pdf)

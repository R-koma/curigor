---
paths:
  - "server/api/routes/speech.py"
  - "server/api/routes/transcription.py"
  - "server/speech/**"
  - "server/transcription/**"
  - "server/repositories/speech_usage_repository.py"
  - "server/repositories/transcription_usage_repository.py"
  - "server/services/transcription_keywords.py"
  - "server/graph/prompts/transcription_keywords.py"
  - "client/lib/audio.ts"
  - "client/lib/audio-levels.ts"
  - "client/lib/end-of-turn.ts"
  - "client/lib/mic-capture.ts"
  - "client/lib/pcm.ts"
  - "client/lib/pcm-stream.ts"
  - "client/lib/speech-bus.ts"
  - "client/lib/speech-probability.ts"
  - "client/lib/speech-text.ts"
  - "client/lib/vad.ts"
  - "client/lib/stt/**"
  - "client/hooks/use-assistant-speech.ts"
  - "client/hooks/use-audio-history.ts"
  - "client/hooks/use-speech-playback.ts"
  - "client/hooks/use-voice-conversation.ts"
  - "client/hooks/use-voice-recorder.ts"
  - "client/components/chat/voice-*.tsx"
  - "client/components/chat/message-speech-button.tsx"
  - "client/public/worklets/**"
  - "client/public/models/**"
---

# 音声（文字起こし・声で話す・読み上げ）

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。STT・VAD・TTS・`VoicePanel`を触る前に関係すると分かっているときは先に読む。

## 音声入力（STT）

- 方式の決定は `docs/adr/007-voice-input-stt.md`。録音（push-to-talk）を `POST /api/transcriptions`（multipart: `audio`・任意の `dialogue_session_id`・任意の `prompt`。`prompt` は `MAX_TRANSCRIPTION_PROMPT_CHARS` 文字まで）で文字起こしし、結果を入力欄に入れてユーザーが確認・修正してから、通常の `user_message` として送る。グラフ・state・eval・capture は音声を知らない
- 新規学習の最初の画面（トピック入力）でも使える。この時点ではセッションが無いので `dialogue_session_id` を省き、使用量は `dialogue_session_id = NULL` で記録し、Langfuse の trace は user だけに紐づく。最初の発言の修正前の文字起こしは `start_learning` の `raw_transcript` で送り、最初の `dialogue_messages` 行に保存する。マイクを出すかは `ChatInput` の `allowVoice` で決める（`sessionId` の有無ではない）。聞き取りカードは選択肢を声で選ばせず、問いを読み上げて自由に話した回答を入力欄で確認して送る（音声対話節）
- 音声は保存しない。修正前の文字起こしは送信時に `raw_transcript` として送り、`dialogue_messages.raw_transcript` / `input_mode`（`text` / `voice` / `voice_auto`）に残す。プロンプトに注入しない値なので `HumanMessage` にも state にも載せない
- 1回 300 秒（クライアントで自動停止・64kbps 固定）、受付 5 MiB、`audio/webm` / `audio/mp4` / `audio/wav`（44 バイトの標準ヘッダー・PCM 16bit モノラルのみ。「声で話す」の発話区間）。ブラウザは `audio/webm;codecs=opus` のようにパラメータ付きで送るので、MIME はパラメータを落として比較する
- 1日の上限は音声の秒数（`DAILY_TRANSCRIPTION_SECONDS`）。WAV の長さは実際のバイト数から計算し（ヘッダーのサイズ欄は信用しない）、webm / mp4 は録音が 64kbps 固定なので `audio_bytes / 8000` 秒とみなす（低ビットレートに偽装したアップロードは過小に数えうる。1 回 5 MiB の上限が頭打ちにする）。文字起こしを呼ぶ前に `transcription_usages`（`audio_seconds`）へ予約として記録し、失敗したら（502 を含む）その行を消して数えない。判定と予約は利用者ごとの advisory lock の中で行い、同時のリクエストがそろって上限を抜けない（`REVIEW_TIMEZONE` の暦日で数える）。不正なアップロード（400・413・415）は予約の前に弾く
- **文字起こしにはセッションの用語の一覧を `keywords` で渡す**（ADR-015）: 一覧は `dialogue_sessions.transcription_keywords` に持ち、`POST /api/transcriptions` が `dialogue_session_id` から読む。まだ無いとき（聞き取りの途中・作成前）はトピック名だけを渡し、`dialogue_session_id` の無い最初の画面では渡さない。一覧は `services/transcription_keywords.py` が「トピック名 + 観点名 + LLM の用語」で作る。WS の `_stream_ai_response` と再開が毎ターン state から出どころ（学習は深さの地図ができた後のトピック・観点名・学習目的、復習はトピック・重点の観点・ノートの要約、インプットはトピックと会話で抜き出した用語 `explore_terms` の表記を新しい順）を作ってバックグラウンドに回し、出どころのハッシュ（`transcription_keywords_source`。プロンプトの fingerprint とモデル名を含む）が同じなら LLM を呼ばない。LLM が失敗したらトピックと観点名だけを保存し、ハッシュを空にして次のターンで作り直す。インプットは LLM を呼ばず、トピックと用語をそのまま一覧にする（`KeywordSource.generate=False`。用語は会話に実際に出た語なので、件数の上限で落ちるのは古い用語から）。プロンプトに注入しない値なので state にも載せない。API は `<` `>` 改行を含む語でリクエストごと拒否するので、`sanitize_keywords` が落とす（件数は `MAX_TRANSCRIPTION_KEYWORDS`、長さは `MAX_TRANSCRIPTION_KEYWORD_CHARS` まで）。入力欄のマイクは prompt にトピック名（`topicTranscriptionPrompt`）を渡し、「以上」の定型文は声で話すだけ。精度の比べ方は `server/evals/transcription.py`（`.claude/rules/server/evals.md`）
- 文字起こしはグラフの外なので、Langfuse には `traced_transcription()` が `transcribe-audio`（generation）として、対話セッションの session に紐づけて送る
- 環境変数: `TRANSCRIPTION_MODEL`（既定 `gpt-transcribe`）。認証は既存の `OPENAI_API_KEY`。OpenAI クライアントは 120 秒・再試行 1 回に絞っている

## 音声対話（声で話す）

- 方式の決定は `docs/adr/010-voice-conversation.md`。学習と復習のチャット画面の入力欄の「声で話す」で始まり、入力欄の場所が `VoicePanel` に置き換わる。速度は端末ごとに `localStorage`（`voice-speed`）へ保存する。グラフ・state・eval・capture は音声を知らない
- 入力は `lib/mic-capture.ts`（`AudioWorklet`（`public/worklets/pcm-capture.js`）で 16kHz・20ms のフレーム）→ `lib/speech-probability.ts`（Silero VAD の声の確率）→ `lib/vad.ts`（区間のヒステリシス）→ `lib/stt/`（`LiveTranscriber`。第 1 段階は区間ごとに WAV で `POST /api/transcriptions` する `segmented`）。状態遷移・割り込み・送信は `useVoiceConversation` に閉じる
- 発話区間は Silero VAD v6（`public/models/silero_vad_16k_op15.onnx`。v6.2.1 の 16kHz 版）の「声の確率」で判定する。`onnxruntime-web/wasm` をメインスレッド・1 スレッドで動かす（`crossOriginIsolated` が要らない）。WASM は Turbopack が `import()` から自動でアセットにするので `public/` に置かない。モデルは 512 サンプル（32ms）ごとに直前の 64 サンプルを先頭に付けて渡すので、`SpeechProbabilityStream` が 20ms のフレームを詰め替え、各フレームは末尾のサンプルを含むチャンクの確率で到着順に VAD へ渡す。区間の開始は `threshold`、終わりは低い `endThreshold` で判定する（確率は発話の途中でも一瞬下がるため）
- モデルを読み込むまでと、読み込み・推論に失敗した後は音量の VAD（開始から `NOISE_CALIBRATION_MS` の周囲の音量で閾値を校正。`thresholdFromNoise`）で判定する。推論が 1 回でも失敗したら、マイクを開き直す（開始・再開）まで確率に戻さない
- `openMicCapture` は準備に失敗したらどの段階でもマイクを手放し、suspended の `AudioContext` は `resume()` する。`useVoiceConversation.start` は `startingRef` と開始ごとのトークンで二重開始を防ぎ、停止・unmount で取り消された開始は取得したマイクを閉じる。文字起こしは mount の effect で作り、unmount で `reset()` する
- 送信の合図は最後の区間の末尾の「以上」（`lib/end-of-turn.ts`）。沈黙では送らない。Enter（`sendNow`）は、応答中なら応答の終わりまで待ってから送る（「以上」と同じ）。`evaluate` は区間が文字起こし中か VAD が発話中のあいだは送らず、失敗した区間は飛ばして送る。30 秒で強制的に区切った区間も同じ評価を通る。送る前に、区間から作った部分（規則で直した文。#753 の編集文は学習者が打った文なので含めない）を `POST /api/transcriptions/format` で整形し、その結果を待ってから送る（6 秒で打ち切り）。整形がどう失敗しても規則で直した文で送り、セッションが無いときは呼ばない。待つ間は `thinking` で、`evaluate` は動かない。待つ間に `stop`・`pause`・`beginEdit`・区間の `reset` を通る経路（言い直し・「話を続ける」を含む）を通ったら送らない（区間は残す）。送れたら `drop` で送った区間だけを消し、待つ間に話し終えた次の発言を続けて評価する。聞き直し（`sendEdited`）の本文は整形しない。送った発言は `voice_auto` で、`stt_method` / `stt_latency_ms`（「以上」の区間の終わりから送信まで。整形の待ちを含む）を `dialogue_messages` に残す。プロンプトに注入しない値なので `HumanMessage` にも state にも載せない
- 区間は独立に文字起こしされるので、発話の途中の間で切れた区間の末尾にもモデルが「。」を付ける。`joinSegments` は最後ではない区間の末尾の「。」を、次の区間が文頭に来ない語（を・の・と呼ばれる・など…。`CONTINUATION_HEAD`）で始まれば消し、そうでなく末尾が助詞・て形・つなぎ言葉（えー・あの）・文頭の副詞（まず・つまり）+「。」なら「、」に直してつなぐ（て形の依頼「読んで。」の後に続きを話すと「、」になるのは受け入れている）。直しは `closeSegments` が区間ごとに行い、送る本文とパネルの区間の表示は同じ結果を使う。`raw_transcript` は直す前の区間をつないだ文（`rawTranscriptOf`）。`closeSegments` は言いよどみも `removeFillers` で取り除く（位置は本文の先頭か「、。，．」・空白の直後。必ず消す語は えー・えっと・えーと・えと・うーん・んー・あー、普通の語と同じ形の あの・その・まあ・なんか は「ー」で伸ばした形か直後に「、」「，」があるときだけ消す）。消して空になった区間は返さない（パネルにも出ない）。eval（`server/evals/transcription.py`）は VAD を通さず句読点も数えないので、この現象は測れない
- 聞き取りカードが最後のメッセージのときは、「以上」で送らずに `onHold` で入力欄へ入れてパネルを閉じる（カードへの回答は取り消せないため）。このとき復元する文字起こしの自動送信の印は付けず、`input_mode = 'voice'` で保存する。鉛筆ボタン（取り消し）もパネルを閉じる
- 声で話しているとき（`conversation.status !== "off"`）と、声の回答を入力欄で確認している間（`restoredTranscript` あり）は、聞き取りカードの代わりに `VoiceIntakePrompt` が問いだけを並べ、冒頭の一文と問いを一度に読み上げる（ADR-011）。確認中も切り替えるのは、`onHold` でパネルが閉じるとカードに戻り、表示が入れ替わるため。読み上げる文面は `intakeSpeechText` で作り、`useChatWebSocket` の speechBus と ▶ の両方が同じ関数を使う（`intake_question` の `content` と文面が違うので、▶ で `msg.content` を読むと保持した音声の文の番号がずれる）。回答は自由文の返信として `extract_intake` が処理する
- `VoicePanel` のキー操作（Enter 送信・Esc 一時停止・Backspace 言い直し）は、入力欄への入力中と dialog / alertdialog / menu の中では無視する。Enter はボタン・リンクにフォーカスがあるときも無視する（そのボタンの操作を奪わないため）
- 聞き取った内容はパネルの文そのもの（ボタン。点線の下線で押せることを示す。一時停止中も押せる）を押すとその場で直せる。`beginEdit` は一時停止してから文字起こし中の区間を待ち、「以上」を除いてつないだ文をテキスト欄に入れる。編集中は `evaluate` を止め（応答の終わりで「以上」の区間が自動送信されないため）、パネル全体のキー操作は効かない（中央の丸は後述の「話を続ける」になる）。`sendEdited` は直した文を `content`、つないだ元の文を `raw_transcript` にして `deliver` を通し（`voice_auto` のまま。`stt_latency_ms` は編集の時間が混ざるので送らない）、送れたらマイクを開き直す。応答中は応答の終わりまで待って送る（待つ間に取り消すと送らない）。送れなかったら編集を残す。取り消し（Esc）は区間を残して再開する。編集中の中央の丸（「話を続ける」）は `continueEdited` で直した文を編集文（`editedPrefix`）として保ち、区間を捨てて再開する。後の発話は編集文の後ろにつながり（句読点は足さない）、送る `content` は直した文 + 後の発話、`raw_transcript` は元の文字起こし + 後の発話になる。「以上」の判定と除去は区間だけにかける（編集文は打ったまま送り、末尾の「以上」でも送らない）。編集文は送信・終了・言い直し・マイクを開き直せなかったときに消え、直した文を空にして続けると言い直しと同じになる。編集を始めたときのカーソルは押した文字の位置（`lib/caret.ts`。表示だけの文字には `data-caret-skip` を付けて数えない）で、キーボードで始めたときと位置が取れないときは末尾
- `ChatInput` は mount 時点で渡された `restoredTranscript` から `transcripts` / `restoredAutoSent` を初期化する。学習・復習の両ページは、送信に成功したときと「声で話す」を始めるときに `restoredTranscript` を捨てる（古い復元が残ると、次に `ChatInput` が mount し直されたときに再適用される）
- 読み上げはクライアントが応答のストリームを文に切り（`lib/speech-text.ts` の `SentenceSplitter`。応答の最初の文が 25 字を超えると 10 字以降の最初の読点で切る）、`POST /api/speech`（JSON: `text`・必須の `dialogue_session_id`・`speed`）へ順に要求する。`speed` は 1 / 1.25 / 1.5 のいずれか（JSON の整数 `1` も受ける）。返りは 24kHz・16bit・モノラルの PCM のストリームで、`useSpeechPlayback` が届いたチャンクを `AudioContext` の時刻軸に隙間なく並べる（同時の要求は 2 件。`inflightRef` の上限）。応答のテキストは `useChatWebSocket` の `speechBus` が `useAssistantSpeech` へ渡す
- 応答は `ChatMessage.speechKey` で識別する。`useChatWebSocket` が応答ごとに発行してメッセージと `speechBus.text(key, text)` の両方に載せ、再開した履歴の AI 応答は `resumed-<セッション ID>-<添字>` になる（セッション ID が無いと、別セッションの同じ位置の応答が保持された音声を取り違える）。再開時は読み上げを止める。取り消しで添字は再利用されるので、添字で応答を指さないこと
- 合成した PCM は `useSpeechPlayback` が `(speechKey, 文の番号)` でページ内に保持する（最大 20 応答）。速度を変えると保持を捨てる。▶（`MessageSpeechButton`）のやり直しは保持を使い、再課金しない。文の番号は `SentenceSplitter` の出力順で、ストリームを読む側（`useAssistantSpeech`。読まない文にも番号を振る）と ▶ の `splitIntoSentences` が同じ分割になることが前提
- `useSpeechPlayback` の unmount の後始末は `AbortController` を作り直す。開発時の Strict Mode が effect を 2 回実行するため、作り直さないと以降の要求がすべて取り消し済みになる
- `sendMessage` は送れたかを返す。`ChatInput` の `onSend` が `false` を返すと、入力欄・文字起こし・自動送信の印を残して案内を出す
- `POST /api/speech` は 1 回 `MAX_SPEECH_CHARS` 文字まで、1 日の上限は `DAILY_SPEECH_CHAR_LIMIT` 文字。合成を呼ぶ前に `speech_usages`（文字数）へ予約として記録し、判定と予約は利用者ごとの advisory lock の中で行う（同時のリクエストがそろって上限を抜けない。`REVIEW_TIMEZONE` の暦日で数える）。最初のチャンクを得る前に失敗したら予約の行を消す。`speech_usages.dialogue_session_id` は `SET NULL`（ノートの削除でセッションを消しても、その日の使用量を戻さない）。外部 API を待つので `DB` 依存を使わない
- `POST /api/speech` は本文を `StreamingResponse` で返す。Langfuse の `synthesize-speech` は `start_speech_trace()` が current にせず作り、ストリームの `finally` で `finish()` する（本文の送信は別タスクで走るため）。予約は最初のチャンクを得たら確定し、以降の失敗・切断では消さない（上流はその時点で課金済み）。上流のストリームは `finally` と `BackgroundTask` の両方で閉じる。`BackgroundTask` に渡すのは `async` のラッパー（`close_stream`）で、`stream.aclose` を直接渡すと Starlette が同期関数として threadpool で呼び、await されない
- **送る前の整形**（`POST /api/transcriptions/format`。JSON: `text`・必須の `dialogue_session_id` → `{text}`）: つないだ文の句読点（途中の「。」を消す・「、」にする、文末に「。」）と言いよどみの削除だけを LLM（`format-transcript`、温度 0）に頼む。`services/transcript_format.py` の `is_deletion_only`（NFKC・句読点・空白・言いよどみを除いたうえで、結果が元の部分列かつ 9 割以上の長さ）を満たさない結果は書き換えとみなし、warning を出して入力をそのまま返す（Langfuse の output は `{"rejected": true}`）。`text` が空・`MAX_TRANSCRIPT_FORMAT_CHARS`（4000）超は 400 `transcript_text_invalid`、他人のセッションは LLM の前に 404。LLM の失敗・`TRANSCRIPT_FORMAT_TIMEOUT_SECONDS`（5 秒）超過は 502 `transcript_format_failed` で、クライアントは規則の文（`closeSegments`）のまま送る。外部 API を待つので `DB` 依存を使わず、所有の確認の間だけ `acquire()` する。言いよどみの語は `removeFillers` と同じ一覧にそろえる
- 環境変数: `SPEECH_MODEL`（既定 `gpt-4o-mini-tts`）・`SPEECH_VOICE`。認証は既存の `OPENAI_API_KEY`
- 自動送信した発言を取り消すと、元の文字起こしと自動送信の印が入力欄の側に復元され、直して送り直すと `raw_transcript` が残り `input_mode` も `voice_auto` のままになる（`lastSentRawRef` / `lastSentAutoRef` → `editingRawTranscript` / `editingAutoSent` → `ChatInput` の `restoredTranscript`）。送り直しを `voice` にすると、訂正のあった発言が `voice_auto` から消えて計測できない
- 読み上げ中・応答中に話し始めたら、`useAssistantSpeech.interrupt()` で読み上げを一時停止する（`useSpeechPlayback.hold()`。鳴っていた文から先を保持し、止めている間に届いた文も溜める。応答中なら、まだ始まっていない次の応答も溜める）。割り込みの発話の終わり（VAD の `end`）から `RESUME_AFTER_INTERRUPT_MS` 発話が無く、文字起こしが返っていて「以上」で終わっておらず、割り込みの区間（割り込みが始まったときの区間の数より後。再開か保持が決まるまで、待ちの間の発話も含む）の文字数（句読点・空白を除く）が `MIN_INTERRUPTION_CHARS` 未満なら、止めた文の頭から再開し（保持した PCM を使い再課金しない）、区間を捨てる。文字数が足りていれば再開せずに区間を残し、ふだんの聞き取りに戻る（「以上」・Enter で送る。沈黙では送らない）。その割り込みの中では、後の短い発話でも再開しない。最後の区間の末尾が「続けて」（`asksToResume`）なら、待たずに再開して区間を捨てる（区間を残した後も同じ）。何も止めていないときの「続けて」はただの発話。「続けて」は文字起こしのプロンプトに入れていない（プロンプトは `server/evals/transcription.py` の `VOICE_PROMPT_BASE` と一致させるため）。発言を送ったら（「以上」・Enter）止めた応答は捨てる（`discardInterrupted`）。一時停止・終了・`speechBus.abort()`・▶・より新しい応答の開始で保持は解け、再開しない（このときは区間を残す）。誤検出を減らすため、読み上げ中だけ発話開始の条件を 300ms に延ばす
- 「読み上げ中は割り込まない」設定（端末ごとに `localStorage` の `voice-no-interrupt`）がオンのときは、`interrupt()` を呼ばない。読み上げが鳴っている間（`isSpeaking`）に始まった区間は VAD を `reset()` して捨てる（AI 自身の声・周囲の声を文字起こしに混ぜないため）。読み上げが終わっても話し続けていれば、そこから新しい区間になる。応答の生成中でまだ鳴っていない間は今までどおり取り込む。読み上げだけを止めるのはパネルの「読み上げを停止」（読み上げ中だけ出る。マイクは止めない）
- `VoicePanel` の状態は中央の丸 1 つで見せる（`listening` / `thinking` は押すと一時停止、`paused` は再開、`speaking` は読み上げの停止。マイクは止めない）。状態の文言は `role="status"` の `sr-only` にだけ置き、画面に常に出す文字は話した内容と初回の「以上」の案内だけにする。イヤホンの案内は設定の中
- **ブラウザは自動再生を制限する**: `AudioContext` はユーザー操作の中で解錠する。入口は「声で話す」（`useVoiceConversation.start`）と ▶（`playMessage`）。再生の直前に suspended なら `resume()` を最大 300ms 待ち、動かなければその応答の残りを捨てる
- 応答の終わりは `speechBus.end()` で知らせるため、`assistant_message_end` 以外で応答が終わる経路（`error`・`pending_message_rolled_back`）でも `end()` を呼ぶこと。呼ばないと次の応答が丸ごと黙る。応答を読み切らずに捨てる経路（`ws.onclose`・`resetSession`）は残りを読み上げないよう `speechBus.abort()` を呼ぶ（`end()` だと途中の文まで読み上げる）
- 声で話していないときの入力欄のマイク（`useVoiceRecorder`。文字起こしを入力欄に入れて確認してから送る）は残っている。これは `input_mode = 'voice'`
- 上流の TTS が本文の途中で失敗すると、サーバーはログを出して `SpeechError` を再送出し、チャンク転送を異常終了させる。クライアントはその文の保持を捨てて失敗の通知を出す（途切れた文を保持して ▶ が再生しないため）
- 一時停止（`pause`。タブが隠れたときも同じ）はマイクを手放し、再開（`resume`）は `start` と同じ `startingRef` + トークンの経路で開き直す（隠れている間は再開しない。開き直しに失敗したら会話を終える）。一時停止中のパネルは応答を読み上げない（`useAssistantSpeech` の `enabled` は `active` / `starting` のみ）。発話の途中で止めた区間は文字起こしに回すだけで、自動では送らない
- Enter（`sendNow`）の `stt_latency_ms` は Enter を押した時刻から測る（「以上」を言わない送信に、古い区間の終わりからの時間を載せないため）。値は 600000ms で頭打ちにする
- `audio/wav` は 16kHz のみ受け付け、ヘッダーだけ（サンプル 0）は 415（長さを秒数で課金するのでレートがずれると過小・過大に数えるため）

## 注意事項

- **multipart のアップロードはハンドラより前に全量受信される**: FastAPI は `UploadFile` を解決する前に multipart 全体をパースし、Starlette は 1 MiB を超えるファイルを一時ファイルへ spool する（リクエスト終了で削除）。`MAX_AUDIO_BYTES` の判定はその後なので、巨大なアップロードを途中で止められない。本番ではリバースプロキシのボディ上限で止めること（#128）

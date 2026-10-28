---
paths:
  - "client/app/**"
  - "client/components/**"
  - "client/__tests__/**"
  - "client/vitest.setup.ts"
  - "client/eslint.config.*"
  - "client/lib/tone.ts"
  - "client/lib/status-display.ts"
  - "client/lib/hints.ts"
  - "client/lib/theme-options.ts"
  - "client/lib/note-tabs.ts"
---

# UI の規約（トークン・部品・スマホ幅・ヒント）

ルートの `CLAUDE.md` から分けた規約。一致するファイルを Read / Edit すると自動で読み込まれる。画面・部品・スタイルを触る前に関係すると分かっているときは先に読む。

- **スマホ幅（`md:` 未満）は `MobileHeader` + `MobileTabBar`、それ以上は `Sidebar` + `Navbar`**（`MainLayoutClient`）。出し分けは CSS（`hidden md:flex` / `md:hidden`）だけで、幅を JS で判定しない。セッション中は `NavbarSlotContext` の `navbarCenter` が non-null で、`MobileTabBar` と `MobileHeader` は描画せず、スロットは `Navbar` が一度だけ描画する（スマホ幅でも出す。別の state を持たない）。`MobileHeader` は区切り線の無い 1 行（メニューのボタンだけ。ページの `h1` は `PageHeading`（見出しと状況の 1 行。左の飾りの線は付けない）で、スマホ幅では `max-md:sr-only`）。ドロワー（`Sheet`）は上にロゴ、真ん中にカレンダー（押すとドロワーを閉じて全画面の Dialog を開く。Dialog は `Sheet` の外に置き、外側のタップ・×・Esc ではドロワーへ戻り、中のリンクでは閉じて移動する）と `RecentItems`（続きから・最近のノート。PC のサイドバーも開いているときはナビの下に出す）、下にアカウントの行を置き（押すとドロワーを閉じて下から `AccountSheet` を開く。写真・テーマの 3 択・ヒント・アカウント設定・ログアウトを並べ、閉じるとドロワーへ戻る。写真の Dialog は入れ子のモーダルがぶつからないよう `SheetContent` の中に置く）、中のリンクを押したとき・ルートが変わったとき・幅が `md` 以上になったときに閉じる。一覧のカード（ダッシュボードの復習・学習履歴）の削除は、タッチ端末では「その他の操作」（⋯）を `pointer-coarse:hidden` で隠し、`SwipeToDelete`（左へスワイプして出る「削除」→ 確認の `AlertDialog`）で行う。振る舞いの分岐（Enter の意味・ショートカットの案内）は幅ではなく入力手段で、`useCoarsePointer()`（`hooks/use-coarse-pointer.ts`）と `pointer-coarse:` / `pointer-fine:` を使う。Radix の Popover / Menu の中身は portal に出るので、`hidden md:flex` で隠した木の中にトリガーを置かない（閉じたはずの内容が見える）。高さは `h-dvh`。方針は ADR-014
- **ノート詳細はスマホ幅だけタブ（ノート / 理解度 / つながり）で分ける**（`components/notes/note-tabs.tsx`）: DOM は 1 つで、各節を `NoteTabSection` で包み、選ばれていないタブの節に `max-md:hidden` を付けるだけ（`md` 以上は全部見える）。Radix の `Tabs` は非選択パネルに `hidden` 属性を付け、Tailwind v4 の `[hidden]` の `!important` に `md:` で勝てないので使わない。理解度タブでフィードバックを観点マップより上に出すため、スマホ幅だけ内側の `main` を `contents`・`aside` を `-order-1` にしている。最初のタブはサーバーが `?feedback=updated` から、ハッシュはクライアントが `tabForHash`（`lib/note-tabs.ts`）で決める。節を足すときは、どのタブに入れるかを決め、`tabForHash` の対応・ページの `tabControls`・`max-md:scroll-mt-14` も足す。「復習する」はスマホ幅では下に固定（`NoteReviewBar`）
- **UI を作る・変えるときは先に `docs/design/ui-guidelines.md` を読む**: アイコンとラベル・ツールチップ・状態の網羅・動き・アクセシビリティなど、判断が要る規則の正本（トークンと lint で守る規則はこの節と ADR-009）
- **`TooltipProvider` はルート（`app/layout.tsx`）に 1 つだけ置く**: 部品ごとに置くと、続けて別のツールチップに乗せたときの遅延の省略が効かない。`Tooltip` を使う部品のテストは `vitest.setup.ts` が `render` を `TooltipProvider` で包むので、テスト側で包まない。アイコンだけのボタンは `aria-label` を付けて `TooltipLabel` で説明する（`button` / `Button` / `a` / `Link` / `div` / `span` の `title` 属性は ESLint が error にする）。メッセージの操作ボタンは `MessageActionButton`
- **色・文字サイズ・重なり順は名前で書く**: `bg-blue-500` のような Tailwind の色名、`text-[10px]`、`z-50`、`h-4 w-4` は書かない（ESLint が error にする。`components/ui/` の shadcn 生成物はサイズ・z-index のルールだけ除外）。色は `app/globals.css` のトークン（`brand` / `success` / `warning` / `caution` / `destructive` / `chart-1`〜`5`。それぞれ `-soft`・`-text` あり）、文字サイズは `text-3xs` / `text-2xs` / `text-prose`、アイコンは `size-N`、重なり順は `z-raised` / `z-menu` / `z-drawer` / `z-overlay`。基調色は `--brand` で、shadcn の `--primary`（白黒）とは別に持つ。目立たせたい塗りのボタンは `--brand-strong`（`--brand` より一段濃い。ダークでは暗くなりすぎて黒に見えないよう、ライトより明るい値）、背景が常に濃い青のところ（LP の CTA）の文字は `--brand-deep`。濃さを変えたいときは `globals.css` のこの値を直し、個別のクラスで色を上書きしない。ライト・ダークの切り替えは変数側で行うので `dark:` で色を上書きしない
- **意味と見た目の対応は 1 か所に置く**: トーンは `lib/tone.ts`、緊急度・観点のカバー状況・フィードバックの種類は `lib/status-display.ts`（`getUrgency` を含む）。復習カードの左ボーダーだけを色付ける `border-l-*` のように、`TONE_CLASSES` の `border`（四辺の色）では足りない場合は `status-display.ts` 側に別に持つ
- **共通部品を先に探す**: 読み込み表示は `Spinner`（`animate-spin` を直接書かない。テストが検査する）と全画面の `LoadingOverlay`、空表示は `EmptyState`。`Spinner` は既定で `aria-hidden`、`label` を渡したときだけ `role="status"` を持つ（`role="status"` の入れ子は `getByRole("status")` を重複させる）。標準的なボタンは `Button`（強調は `variant="brand"`）を使う
- **直書きを許す例外**: `app/opengraph-image.tsx` と `app/global-error.tsx` の hex（CSS 変数が効かない環境で描画する。`opengraph-image.tsx` の色は `--brand-*` の blue と揃える）、`lib/email/otp-email.ts` の hex（メールでは CSS 変数が効かない。色は `--brand` と揃える）、ロゴの hex（`app/icon.svg`・`app/apple-icon.tsx`・`components/brand/app-logo.tsx`・`components/brand/google-logo.tsx`。ロゴの色はテーマで変えない。Google のロゴは Google のブランドガイドラインの色と形のまま使う。`--brand` はダークで明るい青に変わるので使わない。`app-logo.tsx` の図形と色は `icon.svg` と一致させ、テストが検査する）、`globals.css` のコードハイライト、暗幕の `bg-black/*`、`text-white` / `bg-white`
- **トークンの見本**: 開発中は `/design-tokens` で全トークンと部品をライト・ダークで確認できる（本番では 404）。トークンを足したら `__tests__/styles/design-tokens.test.ts` の一覧と見本ページにも足す
- **UI の確認用に作った一時的な見本ページ（`app/<名前>-preview/`）は、コミットと PR が終わったら削除する**: main に残さない。コミットには含めず、この節にも一覧を足さない
- **使い方のヒントは場面ごとに初めて来たときだけ出し、閉じたらユーザーごとに `user_hint_dismissals` へ記録する**: 部品は `UsageHint`（対象の近くに差し込む帯。何も覆わない）、文面と ID は `lib/hints.ts`（ID はサーバーの `schemas/hint.py` の `HintId` とマイグレーションの一覧に揃える）。状態は `UsageHintsProvider`（`MainLayoutClient`）が 1 回だけ取得し、取得前・失敗時は何も出さない。1 画面に 1 つまでなので、複数の場面が重なる学習画面は `useActiveHint` に優先順の候補を渡して 1 つに絞る。AI がこれから問う内容はヒントに書かない。導入の時点でノートがあったユーザーは、マイグレーションで全ヒントを閉じた扱いにしている。アカウント欄の「ヒントをもう一度表示する」が記録を全消去する
- **アカウント欄（アイコン・ユーザー名・テーマ切り替え）はサイドバーの一番下**（`SidebarAccount`）: 折りたたみ中はアイコンだけ、開いているときは左からアイコン・名前・テーマ切り替え。メニューにはテーマの 3 択（ライト・ダーク・自動。`lib/theme-options.ts` をスマホの `AccountSheet` と共有）を出す。名前の横のボタンは `resolvedTheme` で明暗を反転する（`theme` は `system` のことがある）。ナビバーは中央のスロットだけを持つ。アイコンが画面の左下に来るため、Next.js の開発用インジケーター（既定は左下でクリックを横取りする）を `next.config.ts` の `devIndicators.position` で右上へ動かしている。左下に固定要素を足すときも同じ衝突に注意
- **アカウントの削除は `/settings`（アカウント設定）にだけ置く**: サイドバーのメニューと `AccountSheet` はログアウトなど毎日使う操作の並びなので、誤って押さないよう削除を出さず、設定ページへのリンクだけを置く。確認の `DeleteAccountDialog` はメールアドレスを入力するまで「削除する」を押せない。手順を変えたらプライバシーポリシーの「7. アカウントの削除」も直す

## 注意事項

- **Node 25 以降は組み込みの `localStorage` が jsdom のものを覆い隠す**: `--localstorage-file` が無いと `window.localStorage` が使えず、`localStorage` を触るテストが `Cannot read properties of undefined` で落ちる。`client/vitest.setup.ts` がメモリ上の `Storage` で補うので、`localStorage` を使うテストにテスト側の回避は要らない（補うのは `clear` が使えないときだけで、本物の `Storage` と違いプロパティ代入と `storage` イベントは再現しない）。Node のバージョンを上げるときは `.nvmrc`・`engines`・CI・`client/Dockerfile` / `Dockerfile.dev`・README をそろえる

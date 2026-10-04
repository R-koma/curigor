# ADR-009: UI の色・サイズ・重なり順を CSS 変数のトークンで管理し、直書きを lint で禁止する

## Status

Accepted（2026-10-04。実装は #407〜#412）

## Context

`client/app/globals.css` には shadcn/ui のグレーの変数しかなく、アプリで実際に使う色は Tailwind の色名として 27 ファイルに直書きされていた。

- 基調の青が二系統に分かれていた（アプリ本体は blue、ランディング・認証画面・OG 画像は indigo）
- 成功・注意の色が同じ組み合わせで 3 か所に重複し、`dark:` の上書きが 46 か所あった
- 意味と色の対応（復習の緊急度・カテゴリー・観点のカバー状況）が画面ごとに別々にあった
- 任意値の文字サイズ・`h-N w-N` と `size-N` の混在・数値の z-index が散在し、読み込み表示は 9 か所で個別実装されていた

## Decision

- 色は `globals.css` の CSS 変数（`:root` と `.dark`）に置き、`@theme inline` で Tailwind に登録する。ライト・ダークの切り替えは変数側で行い、`dark:` で色を上書きしない
- 基調色は blue。`--primary`（白黒）は変えず、`--brand` を別に足す
- 意味と見た目の対応は `lib/tone.ts` と `lib/status-display.ts` に集める
- 読み込み表示・空表示・全画面の読み込みは `Spinner` / `EmptyState` / `LoadingOverlay` に共通化する
- 文字サイズ・アイコン・重なり順は名前付きのユーティリティ（`text-3xs` / `size-N` / `z-raised` など）に寄せる
- 直書きは ESLint の `no-restricted-syntax` で error にする。shadcn の生成物（`components/ui/`）にはサイズ・z-index のルールだけ当てない

## Reasons

| 案 | 評価 |
| --- | --- |
| CSS 変数＋Tailwind ユーティリティ（採用） | 既存の shadcn の仕組みの延長で、ダークモードを変数側で閉じられる。新しい依存がない |
| クラス文字列を TypeScript の定数に集める | `dark:` の重複が残り、Tailwind の色名を直書きする場所が定数に移るだけになる |
| Style Dictionary などのトークン生成 | この規模ではビルドの仕組みが重い |

- `--primary` を青にすると shadcn 部品の primary がすべて青になり、全画面の見た目が変わる。白黒基調に青の差し色という今の見た目を残すため、`--brand` を別にした
- lint を error にしたのは、決めても新しいコードが直書きに戻ると意味がないため。置き換えを終えた最後のフェーズで有効にして、CI を落とさずに移行した

## Consequences

- 基調色の変更は `globals.css` の数行で済む。新しい UI は既存の名前と部品から選べる
- `text-white` / `bg-white` / `bg-black/*` と hex（`opengraph-image.tsx` / `global-error.tsx`）は lint の対象外。OG 画像の色は `--brand-*` と手で揃える必要がある
- 独自 UI のボタン（ホバーで現れるアイコンボタン、チップ、タブなど）は `Button` に寄せていない
- `Button` の中のアイコンは `size-N` を書くと指定どおりの大きさになる（`h-N w-N` は `Button` の `size-4` に上書きされていた）
- トークンを足したら `__tests__/styles/design-tokens.test.ts` と `/design-tokens` の見本ページにも足す

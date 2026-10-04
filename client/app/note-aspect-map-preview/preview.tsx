"use client";

import {
  NoteAspectMap,
  type AspectMap,
} from "@/components/notes/note-aspect-map";
import type { IntakeSummary } from "@/hooks/use-chat-websocket";

const ASPECT_MAP: AspectMap = {
  root: "文字列の書式",
  aspects: [
    {
      name: "値の埋め込み方",
      summary: "文字列の中に変数の値を差し込む方法",
      coverage: "covered",
      children: [
        {
          name: "f 文字列",
          summary: "式をそのまま波括弧に書ける",
          coverage: "partial",
        },
      ],
    },
    {
      name: "エスケープの扱い",
      summary: "波括弧そのものを出力したいときの書き方",
      coverage: "uncovered",
    },
  ],
};

const SAMPLES: { title: string; intake: IntakeSummary | null }[] = [
  {
    title: "前提あり（3 項目）",
    intake: {
      purpose: "仕事で使うので、基礎をひと通り説明できるようになりたい",
      source: "入門書",
      prior_knowledge: "初めて学ぶ",
    },
  },
  {
    title: "前提の一部だけ",
    intake: { purpose: "", source: "入門書", prior_knowledge: "" },
  },
  {
    title: "前提なし（既存ノート・3 項目とも空）",
    intake: null,
  },
];

export function NoteAspectMapPreview() {
  return (
    <div className="mx-auto max-w-3xl space-y-10 p-6">
      {SAMPLES.map(({ title, intake }) => (
        <div key={title} className="space-y-3">
          <p className="text-sm font-semibold">{title}</p>
          <NoteAspectMap aspectMap={ASPECT_MAP} intake={intake} />
        </div>
      ))}
    </div>
  );
}

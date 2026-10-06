"use client";

import { useState } from "react";

import { IntakeCardView } from "@/components/chat/intake-card";
import type { IntakeCard, IntakeQuestion } from "@/lib/intake";

const topicQuestion = (labels: string[]): IntakeQuestion => ({
  key: "topic",
  header: "トピック",
  question: "何について学びますか？",
  options: labels.map((label) => ({ label, description: "" })),
  multi_select: false,
  preselected: [],
});

const BASE: IntakeQuestion[] = [
  {
    key: "purpose",
    header: "目的",
    question: "今回、何ができるようになりたいですか？",
    options: [
      { label: "基礎を理解したい", description: "仕組みや用語を押さえたい" },
      { label: "仕事・実務で使いたい", description: "" },
      { label: "試験・資格の対策", description: "" },
    ],
    multi_select: false,
    preselected: [],
  },
  {
    key: "source",
    header: "教材",
    question: "何を使って学びますか？（複数選択可）",
    options: [
      { label: "書籍", description: "" },
      { label: "動画・オンライン講座", description: "" },
    ],
    multi_select: true,
    preselected: [],
  },
  {
    key: "prior_knowledge",
    header: "今の理解",
    question: "このトピックについて、今どのくらい知っていますか？",
    options: [
      { label: "初めて学ぶ", description: "ほとんど知らない" },
      { label: "聞いたことはある", description: "" },
    ],
    multi_select: false,
    preselected: [],
  },
];

const LONG_LABEL =
  "Linux カーネルのプロセススケジューラとメモリ管理の仕組みの全体像";

const SAMPLES: { title: string; card: IntakeCard; disabled?: boolean }[] = [
  { title: "トピックは明確（従来のカード）", card: { questions: BASE } },
  {
    title: "トピックを確かめる・候補 3 件",
    card: {
      questions: [
        topicQuestion([
          "Linux の仕組み",
          "TCP/IP の仕組み",
          "ブラウザの仕組み",
        ]),
        ...BASE,
      ],
    },
  },
  {
    title: "トピックを確かめる・候補なし（入力欄だけ）",
    card: { questions: [topicQuestion([]), ...BASE] },
  },
  {
    title: "長い候補ラベル",
    card: {
      questions: [topicQuestion([LONG_LABEL, "短い候補"]), ...BASE],
    },
  },
  {
    title: "目的を聞かない・トピックを確かめる",
    card: { questions: [topicQuestion([]), ...BASE.slice(1)] },
  },
  {
    title: "送信中",
    card: { questions: [topicQuestion([]), ...BASE] },
    disabled: true,
  },
];

export function IntakeCardPreview() {
  const [submitted, setSubmitted] = useState<Record<string, string>>({});
  return (
    <div className="mx-auto max-w-3xl space-y-10 p-6">
      {SAMPLES.map(({ title, card, disabled }) => (
        <section key={title} className="space-y-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          <IntakeCardView
            card={card}
            disabled={disabled}
            onSubmit={(content) =>
              setSubmitted((prev) => ({ ...prev, [title]: content }))
            }
          />
          {submitted[title] && (
            <pre className="rounded-xl bg-muted p-3 text-xs whitespace-pre-wrap text-muted-foreground">
              {submitted[title]}
            </pre>
          )}
        </section>
      ))}
    </div>
  );
}
